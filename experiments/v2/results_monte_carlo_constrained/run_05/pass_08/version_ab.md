# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables.
2. This policy applies immediately to all current and future use of AI tools, regardless of whether a tool was in use before this policy's effective date.
3. GitHub Copilot Business is the sole approved AI tool; 80 seats are allocated to engineers and managed by the company.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) is the sole approved AI coding assistant. It may be used for code completion, test generation, and documentation, provided no customer PII or financial data is included in the prompt or accepted suggestion input.
2. No AI writing tool is currently approved for any employee. Any employee seeking approval for an AI writing tool must submit a written request to Legal; approvals draw from the $50K annual tooling budget.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer PII, financial data, or database schemas into any AI service is prohibited. *(Motivating facts: Incident #1 schema exposure; outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses for any work-related task is prohibited. This includes AI writing tools used for sales email drafting. *(Motivating facts: Incident #2 verbatim copyrighted copy in AI-drafted sales email; outside counsel DPA violation flag; pending FedRAMP authorization.)*
3. **No AI-generated code committed without license review.** All AI-generated code requires pull request reviewer confirmation that no third-party license headers or GPL markers are present before merge. *(Motivating facts: Incident #3 GPL header commit; outside counsel copyright non-ownership flag.)*
4. **No AI-generated content distributed externally without IP review.** The authoring employee must verify AI-assisted content against source material before any external distribution. *(Motivating fact: Incident #2 verbatim competitor copyrighted copy.)*
5. **Slack AI features must remain disabled.** No employee may enable or request enablement of Slack AI features. *(Motivating facts: Slack AI features are currently disabled; outside counsel DPA violation flag applies to any AI service processing company or customer data; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*

---

## Enforcement

1. Violations of Prohibited Uses items 1–2 are security incidents. Employees must self-report to their manager and Legal within 24 hours; managers must escalate to Legal immediately. Failure to self-report is itself a violation. Both the employee and manager are subject to disciplinary action.
2. Violations of Prohibited Uses items 3–5 must be reported by the discovering employee or reviewer to their manager and Legal within 48 hours. The responsible employee is subject to disciplinary action; repeated violations escalate to termination review.
3. Pull request reviewers who approve merges containing AI-generated code without confirming the absence of license markers share accountability for the resulting violation.
4. Compliance with this policy is a condition of employment. Violations are subject to disciplinary action up to and including termination.