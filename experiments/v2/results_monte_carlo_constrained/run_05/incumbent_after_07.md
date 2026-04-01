# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables.
2. This policy applies immediately to all current and future use of AI tools, regardless of whether a tool was in use before this policy's effective date.
3. GitHub Copilot Business is licensed for 80 of 120 engineers; seat allocation is managed by the company.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) is the sole approved AI coding assistant. It may be used for code completion, test generation, and documentation on codebases containing no customer PII or financial data.
2. GitHub Copilot Business is the sole approved AI writing assistant. Any AI-assisted content intended for external distribution must be reviewed, edited, and verified by the authoring employee before sending.
3. Additional AI tools require written approval before use and are funded from the $50K annual tooling budget.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer PII, financial data, or database schemas into any AI service is prohibited. *(Motivating facts: Incident #1 schema exposure; outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unapproved external AI services.** Using AI tools not listed in Permitted Uses for any work-related task is prohibited. *(Motivating facts: Outside counsel DPA violation flag; pending FedRAMP authorization.)*
3. **No AI-generated code committed without license review.** All AI-generated code requires pull request reviewer confirmation of no third-party license headers or GPL markers before merge. *(Motivating facts: Incident #3 GPL header commit; outside counsel copyright non-ownership flag.)*
4. **No AI-generated content distributed externally without IP review.** AI-assisted content must be verified against source material by the authoring employee before external distribution. *(Motivating fact: Incident #2 verbatim competitor copyrighted copy.)*
5. **Slack AI features must not be enabled.** No employee may configure or request re-enablement of Slack AI features. *(Motivating facts: Outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations, which apply to any AI service processing company or customer data.)*

---

## Enforcement

1. Violations of Prohibited Use items 1–2 are reportable security incidents. Employees must self-report to their manager and to Legal within 24 hours; managers must escalate to Legal immediately. Failure to self-report is itself a violation.
2. The authoring employee is responsible for confirming that AI-assisted outbound communications have been reviewed and edited before external distribution, as required by Permitted Uses item 2.
3. The pull request reviewer confirms AI-generated code is free of license markers before approving merge, as required by Prohibited Uses item 3.
4. Compliance with this policy is a condition of employment. Violations are subject to disciplinary action up to and including termination.