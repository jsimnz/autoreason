# AI Tool Usage Policy
**Effective Date:** [Date] | **Owner:** CTO & General Counsel | **Review Cycle:** Quarterly

---

## Scope

1. This policy applies to all 200 employees, contractors, and interns across engineering, sales, and all other functions.
2. This policy governs any use of AI tools for work-related tasks, including coding, writing, data analysis, and customer communications.
3. This policy supersedes all prior informal practices immediately upon issuance.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant. Use is limited to the 80 licensed seats currently provisioned; seat allocation is managed by Engineering leadership.
2. Engineers may use GitHub Copilot for code suggestions, boilerplate generation, and test writing on internal or proprietary codebases that contain no customer PII or financial data.
3. Sales staff may use AI-assisted drafting tools only when integrated natively into approved platforms. All AI-generated customer-facing content requires human review and approval before sending.
4. Requests for additional AI tools must be submitted to the CTO and Legal for review. The $50,000 annual AI tooling budget governs all new approvals.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, database schemas, or any customer-identifiable information into third-party AI tools (including ChatGPT, Claude, or any non-approved service) is prohibited. *(Motivating facts: Incident 1 — engineer pasted customer database schema into ChatGPT; outside counsel confirmation that this likely violates existing DPA terms; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects without human review for accuracy, originality, and legal compliance. *(Motivating fact: Incident 2 — sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code committed without license review.** Code produced by AI tools may not be committed to any repository without a developer confirming no third-party license headers or GPL-encumbered content are present. *(Motivating facts: Incident 3 — intern committed code with a GPL license header from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
4. **Slack AI features remain disabled.** Enabling or circumventing the disabled AI features in company Slack is prohibited.
5. **No unapproved AI tools on company systems.** Installing or accessing non-approved AI services via company devices, accounts, or networks is prohibited.

---

## Enforcement

1. Violations are reported to the employee's direct manager, the CTO, and Legal within 24 hours of discovery.
2. Incidents involving customer data exposure are treated as security incidents under the existing SOC2 incident response procedure and trigger mandatory breach assessment.
3. Code review gates in GitHub enforce the license-review requirement; no merge proceeds without reviewer sign-off. No new tooling is required.
4. First violations result in mandatory remediation training and a written warning. Second violations result in disciplinary action up to and including termination.
5. Managers are accountable for their team's compliance. Quarterly access reviews will audit GitHub Copilot seat usage against this policy.