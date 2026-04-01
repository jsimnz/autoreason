# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy applies to all 200 employees and interns of the company.
2. This policy governs all use of AI-assisted tools for any work-related task, including code generation, written communications, and email drafting.
3. Any AI tool not listed under Permitted Uses is prohibited for all work-related tasks.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant. Seats are allocated to engineers by Engineering leadership, documented in the IT provisioning log, and capped at 80 seats total.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files and contexts that do not contain customer PII, financial data, or database schemas.
3. All AI-generated code must be reviewed by the assigned PR reviewer before commit. The PR reviewer must confirm output contains no third-party license notices before approving the pull request.
4. Any request to approve an additional AI tool must be submitted to Legal and IT as a budget request against the $50K annual AI tooling allocation before any use begins.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: Incident #1 — engineer pasted customer database schema into ChatGPT; outside counsel flagged DPA violation risk; GDPR obligations for EU customers; SOC2 Type II certification requirements; pending FedRAMP authorization.)*
2. **No AI-generated written content containing third-party copyrighted material.** Employees must not submit, send, or publish written content produced by any AI tool that reproduces third-party copyrighted text verbatim. *(Motivating fact: Incident #2 — sales rep transmitted AI-generated email containing a competitor's copyrighted marketing copy verbatim.)*
3. **No committing AI-generated code containing third-party license notices.** Employees must not commit AI-generated code that includes third-party license headers or notices. *(Motivating facts: Incident #3 — intern committed a GPL license notice sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management, within the 80-seat hard cap documented in the IT provisioning log.
2. PR approval is the existing gate at which the assigned reviewer must confirm no third-party license notices are present in AI-generated code. Approving a non-compliant PR constitutes a policy violation by the reviewer.
3. IT must verify, using the existing Slack admin console, on the first business day of each month, that Slack AI features remain disabled. Any re-enabled feature must be disabled within 24 hours and reported to Legal.
4. Suspected violations must be reported to Legal and Security via the existing incident reporting channel within 24 hours of discovery.
5. Any confirmed policy violation results in immediate suspension of AI tool access by IT, pending a written reinstatement or termination decision by the employee's manager and HR.