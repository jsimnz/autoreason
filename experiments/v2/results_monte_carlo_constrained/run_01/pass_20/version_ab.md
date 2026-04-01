# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy applies to all employees, contractors, and interns performing work for the company.
2. It governs all AI-powered tools—code assistants, writing assistants, and generative models—used for company work, including personal accounts and free-tier tools used for company purposes.
3. AI-generated code and content may not be copyrightable; the company makes no ownership assertion over unmodified AI outputs.

---

## Permitted Uses

1. GitHub Copilot Business is the sole approved AI coding tool. Engineering leadership assigns the 80 licensed seats to named individuals via existing GitHub Copilot Business seat controls.
2. Seat-holders may use GitHub Copilot Business for code completion, boilerplate generation, and test writing. No IP ownership claim may be asserted over unmodified AI output.
3. All AI-generated code must pass the existing pull-request review process before merge.
4. Additional AI tools require written approval from the relevant department head and Legal before use begins. Approved tools must not cause total AI tooling spend to exceed $50K/year; when the budget is exhausted, no further approvals occur until the next budget cycle.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—engineer pasted a customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms and creates GDPR liability for EU customer data.]*
2. **No AI-generated external content without copyright review.** AI-generated text for external distribution requires Legal to confirm no third-party copyrighted material is present before sending. *[Basis: Incident 2—sales rep distributed AI-generated text containing a competitor's copyrighted marketing copy verbatim; outside counsel flagged copyright infringement risk in AI-generated content.]*
3. **No commits with third-party license headers.** Pull-request reviewers must reject any commit carrying an AI-generated third-party license header. *[Basis: Incident 3—intern committed AI-generated code carrying a GPL license header from AI training data.]*
4. **No unapproved AI tools.** No employee may use any AI tool not approved under Permitted Uses item 4. *[Basis: Outside counsel confirmed that inputting company or customer data into third-party AI services violates existing DPA terms; the company holds GDPR obligations for EU customers.]*
5. **Slack AI features remain disabled.** No employee may enable AI features within company Slack. *[Basis: Outside counsel confirmed that inputting customer data into third-party AI services violates existing DPA terms; enabling Slack AI features would expose customer PII and financial data processed through Slack to that risk.]*

---

## Enforcement

1. The assigned reviewer confirms AI-generated content complies with this policy before approving any code merge or external output.
2. Any violation is reported to Legal through the existing Legal intake process within one business day of discovery.
3. Upon Legal's confirmation of a violation via the intake process, the violation is recorded in the employee's HR file.
4. A confirmed violation triggers a mandatory manager review within five business days.
5. A confirmed violation results in Engineering leadership revoking the employee's access to the relevant approved AI tool through existing seat or access controls. If the employee holds no such access, item 4 constitutes the procedural consequence.
6. Confirmed violations are subject to disciplinary action up to and including termination, administered through the existing HR disciplinary process.