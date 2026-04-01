# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables. "Customer data" means any PII, financial data, database schemas, or configuration files that identify or are derived from customer environments.
2. GitHub Copilot Business is the sole approved AI tool. The 80 licensed seats are allocated to engineering roles. Employees without an assigned seat have no approved AI tool and no permitted AI use for any work-related task.
3. Company Slack AI features are disabled and unavailable under this policy.
4. A $50K annual budget is allocated for additional AI tooling. No tool outside Permitted Uses may be used until approved per Enforcement item 4.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, test generation, and documentation on files that do not contain customer data.
2. All AI-generated code is subject to pull request reviewer approval before merge, using existing pull request workflows.
3. All AI-generated external written content is subject to manager approval before delivery, using existing email and communications approval chains.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer data into any AI service — including approved tools — is prohibited. *(Motivating facts: Incident #1, engineer pasted customer database schema into ChatGPT; SOC2 Type II certification requirements; GDPR obligations for EU customers; outside counsel determination that inputting customer data into third-party AI services likely violates existing DPA terms.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses for any work-related task is prohibited. *(Motivating facts: Incident #2, AI-generated sales text contained verbatim competitor copyrighted marketing copy; Incident #3, AI-generated code contained a GPL license header committed to the codebase.)*
3. **No AI-generated content merged or delivered without IP review.** Pull request reviewers must reject code containing third-party license headers or GPL markers. Managers must reject external communications containing verbatim third-party copyrighted material. *(Motivating facts: Incident #2 verbatim copyrighted copy; Incident #3 GPL header in committed code; outside counsel determination that AI-generated code may not be copyrightable.)*
4. **No new AI tool approved or used without Legal clearance.** No AI tool outside Permitted Uses may be used until Legal confirms in writing that its use does not violate existing DPA terms and does not jeopardize the pending FedRAMP authorization. *(Motivating facts: Outside counsel DPA flag; pending FedRAMP authorization with Q3 target.)*

---

## Enforcement

1. Violations of Prohibited Uses items 1–2 result in immediate disciplinary action up to and including termination.
2. Violations of Prohibited Uses item 3 require reversion or withholding of the affected content and disciplinary review of both the submitting employee and the approving reviewer. Repeated violations escalate to termination.
3. Violations of Prohibited Uses item 4 are escalated immediately to Legal and the CEO, the tool is suspended pending written Legal clearance, and disciplinary action up to and including termination follows.
4. Requests to approve new AI tools are submitted to Legal and Security in writing. Legal confirms in writing that the tool does not violate existing DPA terms and does not jeopardize FedRAMP authorization before any use proceeds. Approved tools are added to Permitted Uses by written amendment signed by the CEO.