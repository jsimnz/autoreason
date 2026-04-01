# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables. "Customer data" means any PII, financial data, database schemas, or configuration files that identify or are derived from customer environments.
2. GitHub Copilot Business (80 licensed seats, allocated to engineering roles) is the sole approved AI tool. Employees without an assigned seat have no approved AI tool.
3. Company Slack AI features are administratively disabled and remain disabled under this policy.
4. Survey data shows 45% of sales staff currently use AI tools for email drafting. No AI tool is approved for sales use. Sales staff are covered by the prohibitions below.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, test generation, and documentation on files containing no customer data.
2. All AI-generated code and written content must receive manager or pull request reviewer approval before merge or external delivery, using existing pull request workflows and email approval chains.
3. The $50K annual AI tooling budget funds existing GitHub Copilot Business seats. Any additional tool requires CEO and Legal approval before purchase or use.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer data into any AI service is prohibited. *(Motivating facts: Incident #1 — engineer pasted customer database schema into ChatGPT; SOC2 Type II certification requirements; GDPR obligations for EU customers; pending FedRAMP authorization; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms.)*
2. **No unapproved AI tools.** Any employee without an assigned GitHub Copilot Business seat, and any employee using any tool not listed in Permitted Uses, is prohibited from using AI tools for work-related tasks. *(Motivating facts: Incident #2 — AI-generated sales copy contained verbatim competitor copyrighted text; Incident #3 — AI-generated code contained a GPL license header committed to the codebase.)*
3. **No third-party IP in merged or delivered content.** Pull request reviewers must reject code containing third-party license headers or GPL markers. Managers must reject external communications containing verbatim third-party copyrighted material. *(Motivating facts: Incident #2 — verbatim copyrighted copy in delivered content; Incident #3 — GPL header committed to codebase; outside counsel finding that AI-generated code may not be copyrightable.)*

---

## Enforcement

1. Violations of Prohibition 1 result in immediate disciplinary action up to and including termination and are reported to Legal for DPA, GDPR, and FedRAMP impact assessment.
2. Violations of Prohibition 2 are detected through pull request review, document review, and manager attestation during performance reviews. Violations result in disciplinary review; repeated violations result in termination.
3. Violations of Prohibition 3 require reversion or withholding of affected content and disciplinary review of both the submitting employee and the approving reviewer; repeated violations result in termination.
4. Engineering managers assign and revoke GitHub Copilot Business seats via the existing admin console. Seat assignments are reviewed quarterly against active engineering headcount.