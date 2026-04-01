# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy applies to all 200 employees and interns of the company.
2. This policy governs all use of AI-assisted tools for any work-related task.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, capped at 80 seats provisioned and tracked in the IT provisioning log.
2. Engineers may use GitHub Copilot Business only in work that does not involve customer PII, financial data, or database schemas. The PR author must confirm this in the PR description; the reviewer must verify before approving.
3. All AI-generated code must pass PR review. The author must declare that no third-party license notices are present; the reviewer must confirm that declaration before approving.
4. Additional AI tools may be approved upon written sign-off by Legal and Security, documented in the IT provisioning log prior to use, within the $50K annual AI tooling budget.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: Incident #1 — engineer pasted customer database schema into ChatGPT; outside counsel flagged DPA violation risk; GDPR obligations for EU customers; SOC2 Type II certification; pending FedRAMP authorization.)*
2. **No verbatim third-party copyrighted content.** Employees must not submit, send, or publish AI-generated content that reproduces third-party copyrighted text verbatim. *(Motivating fact: Incident #2 — sales rep transmitted AI-generated email containing a competitor's copyrighted marketing copy verbatim.)*
3. **No unapproved AI writing tools.** Sales and non-engineering employees must not use any AI writing tool not approved under Permitted Use #4. *(Motivating facts: Incident #2; 45% of sales using unapproved tools with no safeguard in place.)*
4. **No committing AI-generated code containing third-party license notices.** Employees must not commit AI-generated code that includes third-party license headers or notices. *(Motivating facts: Incident #3 — intern committed a GPL license notice sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
5. **No delivering AI-generated code to customers as proprietary work product.** AI-generated code must not be included in customer deliverables represented as the company's original intellectual property. *(Motivating fact: Outside counsel flagged that AI-generated code may not be copyrightable.)*
6. **No use of Slack AI features.** Employees must not enable or use any AI feature within the company Slack instance. *(Motivating fact: Slack AI features are currently disabled per company configuration; no legal or security review of those features has been completed.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management within the 80-seat hard cap documented in the IT provisioning log.
2. The PR approval gate requires reviewer confirmation of the author's data and license declarations. Approving without those confirmations is a policy violation by the reviewer.
3. IT must disable any Slack AI feature found re-enabled and report to Legal within 24 hours of discovery.
4. All suspected violations must be reported to Legal and Security via the existing incident reporting channel within 24 hours of discovery.
5. For violations involving AI-generated content already distributed where tool-access revocation is inapplicable — including copyright incidents under Prohibited Use #2 — the employee's manager and Legal must conduct a written review within five business days and issue a documented remediation or termination decision.
6. All other confirmed violations result in immediate suspension of AI tool access by IT, pending a written reinstatement or termination decision by the employee's manager and HR.