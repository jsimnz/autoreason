I'll address each problem in turn, then present the revised document.

**Problem 1 (word count):** Cut explanatory prose throughout, shorten basis citations, and compress Enforcement.
**Problem 2 (Enforcement item 2 prose paragraph):** Split the escalation logic into discrete numbered items.
**Problem 3 (Permitted Uses item 3 prose):** Strip the parenthetical commentary; retain only the policy rule.
**Problem 4 (45% sales usage unaddressed):** Add an affirmative permitted use item covering AI-assisted email drafting for sales, subject to the existing manager-approval control.
**Problem 5 ($50K budget as enforcement mechanism):** Remove the budget cap from Permitted Uses; the budget is a financial fact, not a policy rule.
**Problem 6 (no prohibition on unapproved AI coding tools):** Add an explicit prohibition on unapproved AI coding tools, citing the 73% informal usage fact.
**Problem 7 (self-referential department head violation):** Remove the self-referential trigger entirely; the escalation chain ends at the department head.
**Problem 8 (FedRAMP cited as binding):** Replace "FedRAMP requirements" with "pending FedRAMP authorization" to reflect the actual base fact.

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

1. **GitHub Copilot Business** is the sole approved AI coding tool. Engineering leadership assigns and revokes the 80 licensed seats; no seat may be shared.
2. Copilot-seated engineers may use GitHub Copilot for code completion, boilerplate generation, and test writing within the licensed environment only.
3. All AI-generated code must receive human reviewer approval before merge.
4. Sales staff may use AI tools approved under item 5 for internal email drafting; all AI-drafted text intended for external distribution requires direct manager approval before sending.
5. Additional AI tools require written approval from both Engineering leadership and Legal before any use begins.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—engineer pasted a customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms and creates GDPR liability.]*
2. **No AI-generated external content without manager approval.** AI-generated text for external distribution may not be sent without direct manager approval. *[Basis: Incident 2—a sales rep distributed AI-generated text containing a competitor's copyrighted marketing copy verbatim.]*
3. **No commits containing AI-generated code with third-party license headers.** Reviewers must reject any pull request carrying such a header. *[Basis: Incident 3—an intern committed AI-generated code carrying a GPL license header originating from AI training data.]*
4. **No unapproved AI coding tools.** Engineers may not use any AI coding tool other than GitHub Copilot Business. *[Basis: 73% of engineers are already using informal AI coding tools with no data-handling controls, creating DPA, GDPR, and IP exposure.]*
5. **Slack AI features must remain disabled.** No employee may request or self-enable AI features within company Slack. *[Basis: Company handles customer PII and financial data subject to DPA terms and GDPR obligations; enabling Slack AI features would route that data through a third-party AI service without approved data processing agreements; doing so would also jeopardize the pending FedRAMP authorization.]*

---

## Enforcement

1. Each manager reviews direct reports' AI tool use through existing code review and output approval processes.
2. Any violation carrying legal liability—customer data exposure, copyright infringement, or license header incidents—must be routed to Legal via the existing Legal intake process within one business day of discovery.
3. If a manager does not complete that routing within one business day, the obligation transfers to the department head.
4. A confirmed violation is recorded in the employee's existing HR file and triggers a mandatory manager review within five business days.
5. Where a confirmed violation involves AI tool access, Engineering leadership revokes that access through existing GitHub Copilot seat controls or Slack administrator controls as applicable.