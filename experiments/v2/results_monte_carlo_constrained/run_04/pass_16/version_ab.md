# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy applies to all 200 employees and interns of the company.
2. This policy governs all use of AI-assisted tools for any work-related task, including code generation, written communications, and email drafting.
3. Any AI tool not listed under Permitted Uses is prohibited for all work-related tasks.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, allocated within the 80 licensed seats by Engineering leadership.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files and contexts that do not contain, reference, query, or model customer PII, financial data, or database schemas.
3. All AI-generated code must be reviewed by the assigned PR reviewer before commit. The PR reviewer must confirm output contains no third-party license notices before approving the pull request.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: Incident #1 — engineer pasted customer database schema into ChatGPT; outside counsel flagged DPA violation risk; GDPR obligations for EU customers; SOC2 Type II certification requirements; pending FedRAMP authorization.)*
2. **No committing AI-generated code or content containing third-party license notices or verbatim copyrighted material.** Employees must not commit AI-generated code or transmit AI-generated content that contains third-party license notices or reproduces third-party copyrighted material verbatim. *(Motivating facts: Incident #2 — sales rep transmitted AI-generated text containing a competitor's copyrighted marketing copy; Incident #3 — intern committed a GPL license notice sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
3. **No representing AI-generated code as original company IP.** AI-generated code must not be represented as original company IP in customer deliverables or contracts. *(Motivating fact: outside counsel flagged that AI-generated code may not be copyrightable.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management within the 80-seat limit.
2. PR approval is the existing gate at which the assigned reviewer must confirm no third-party license notices are present in AI-generated code. Approving a non-compliant PR constitutes a policy violation by the reviewer.
3. Slack AI features remain disabled via existing platform controls.
4. Suspected violations must be reported to Legal and Security via the existing incident reporting channel within 24 hours of discovery.
5. Any confirmed policy violation results in immediate suspension of AI tool access by IT, pending a written reinstatement or termination decision by the employee's manager and HR.