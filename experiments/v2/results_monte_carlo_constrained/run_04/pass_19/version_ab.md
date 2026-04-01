# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy applies to all 200 employees and interns of the company.
2. This policy governs all use of AI-assisted tools for work-related tasks, limited to: code generation, written communications, and email drafting.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant. Seats are allocated to engineers by Engineering leadership, documented in the IT provisioning log, and capped at 80 seats total.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on contexts containing no customer PII, financial data, or database schemas.
3. All AI-generated code must be reviewed by the assigned PR reviewer before commit. The author must declare in the PR that the output contains no third-party license notices; the reviewer must confirm that declaration before approving.
4. No AI writing tool is approved for sales or any other non-engineering function.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: Incident #1 — engineer pasted customer database schema into ChatGPT; outside counsel flagged DPA violation risk; GDPR obligations for EU customers; SOC2 Type II certification; pending FedRAMP authorization.)*
2. **No AI-generated content containing verbatim third-party copyrighted material.** Employees must not submit, send, or publish AI-generated content that reproduces third-party copyrighted text verbatim. *(Motivating fact: Incident #2 — sales rep transmitted AI-generated email containing a competitor's copyrighted marketing copy verbatim.)*
3. **No committing AI-generated code containing third-party license notices.** Employees must not commit AI-generated code that includes third-party license headers or notices. *(Motivating facts: Incident #3 — intern committed a GPL license notice sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
4. **No use of Slack AI features.** Employees must not enable or use any AI feature within the company Slack instance. *(Motivating fact: Slack AI features are currently disabled per company configuration; no legal or security review of those features has been completed.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management, within the 80-seat hard cap documented in the IT provisioning log.
2. PR approval is the gate at which the assigned reviewer confirms the author's declaration that no third-party license notices are present. Approving a PR without that declaration constitutes a policy violation by the reviewer.
3. IT must verify, using the existing Slack admin console, that Slack AI features remain disabled whenever a Slack platform update is released. Any re-enabled feature must be disabled and reported to Legal.
4. Managers must report any AI-generated outbound communication found to contain verbatim third-party copyrighted material to Legal via the existing incident reporting channel within 24 hours of discovery.
5. All other suspected violations must be reported to Legal and Security via the existing incident reporting channel within 24 hours of discovery.
6. Any confirmed policy violation results in immediate suspension of AI tool access by IT, pending a written reinstatement or termination decision by the employee's manager and HR.