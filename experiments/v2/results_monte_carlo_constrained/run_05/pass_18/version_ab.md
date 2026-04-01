# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables. "Customer data" means any PII, financial data, database schemas, or configuration files that identify or are derived from customer environments.
2. GitHub Copilot Business is the sole approved AI tool. The 80 licensed seats are allocated to engineering roles. Employees without an assigned seat have no approved AI tool.
3. Company Slack AI features are disabled and unavailable under this policy.
4. Survey data shows 45% of sales staff are already using AI tools for email drafting. No AI tool is approved for sales use. Sales staff are covered by the prohibitions below.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, test generation, and documentation on files that contain no customer data.
2. All AI-generated code and written content are subject to manager or pull request reviewer approval before merge or delivery, using existing pull request workflows and email approval chains.
3. The $50K annual AI tooling budget funds the 80 GitHub Copilot Business seats. Remaining budget may fund additional tools only after Legal confirms in writing that each tool does not violate existing DPA terms and does not jeopardize the pending FedRAMP authorization. No additional tool may be used before that written confirmation is received.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer data into any AI service is prohibited. *(Motivating facts: Incident #1, engineer pasted customer database schema into ChatGPT; SOC2 Type II certification requirements; GDPR obligations for EU customers; outside counsel determination that inputting customer data into third-party AI services likely violates existing DPA terms.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses for any work-related task is prohibited. *(Motivating facts: Incident #2, AI-generated sales text contained verbatim competitor copyrighted marketing copy; Incident #3, AI-generated code contained a GPL license header committed to the codebase.)*
3. **No AI-generated content merged or delivered without IP review.** Pull request reviewers must reject code containing third-party license headers or GPL markers. Managers must reject external communications containing verbatim third-party copyrighted material. *(Motivating facts: Incident #2 verbatim copyrighted copy; Incident #3 GPL header in committed code; outside counsel determination that AI-generated code may not be copyrightable.)*

---

## Enforcement

1. Violations of Prohibited Uses item 1 result in immediate disciplinary action up to and including termination, and are reported to Legal for assessment of DPA, GDPR, and FedRAMP impact.
2. Violations of Prohibited Uses item 2 result in disciplinary review; repeated violations result in termination.
3. Violations of Prohibited Uses item 3 require reversion or withholding of the affected content and disciplinary review of both the submitting employee and the approving reviewer; repeated violations result in termination.
4. Manager and pull request reviewer approval of all AI-generated code and external content is mandatory before merge or delivery, using existing approval workflows.