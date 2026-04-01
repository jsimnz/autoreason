# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee for company work.
2. Legal and Engineering leadership are jointly responsible for operational enforcement of this policy.
3. Use of personal or free-tier AI tools for company work is subject to this policy.

---

## Permitted Uses

1. GitHub Copilot Business is the sole approved AI coding tool. Engineering leadership assigns the 80 licensed seats to named individuals through existing GitHub Copilot Business seat controls.
2. Copilot-seated engineers may use GitHub Copilot Business for code completion, boilerplate generation, and test writing.
3. AI-generated code must pass the existing pull-request review process before merge.
4. Department head and Legal approval in writing authorizes use of additional AI tools within the $50K annual budget; no use begins before that approval is documented.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—engineer pasted a customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms and creates GDPR liability.]*
2. **No AI-generated external content without manager approval.** AI-generated text for external distribution requires direct manager approval before sending. *[Basis: Incident 2—sales rep distributed AI-generated text containing a competitor's copyrighted marketing copy verbatim; outside counsel flagged copyright infringement risk in AI-generated content.]*
3. **No commits with third-party license headers.** Reviewers must reject any pull request carrying an AI-generated third-party license header. *[Basis: Incident 3—intern committed AI-generated code carrying a GPL license header from AI training data.]*
4. **No unapproved AI tools.** No employee may use any AI tool not approved under Permitted Uses item 4. *[Basis: 73% of engineers and 45% of sales staff already use uncontrolled tools, creating DPA, GDPR, IP, and FedRAMP authorization exposure.]*
5. **Slack AI features must remain disabled.** No employee may enable AI features within company Slack. *[Basis: Company Slack AI features are currently disabled; enabling them risks GDPR compliance and the pending FedRAMP authorization.]*

---

## Enforcement

1. The assigned reviewer confirms AI-generated content complies with this policy before approving any code merge or external output.
2. Any violation involving customer data, copyright infringement, or third-party license headers is reported to Legal through the existing Legal intake process within one business day of discovery.
3. A confirmed violation is recorded in the employee's HR file.
4. A confirmed violation triggers a mandatory manager review within five business days.
5. A confirmed violation involving GitHub Copilot Business access results in Engineering leadership revoking that seat through existing GitHub Copilot Business seat controls.