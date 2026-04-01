**Changes made:**

- **Problem 1:** Removed meta-commentary and changelog. Document is now the policy memo only.
- **Problem 2:** Shortened items throughout to bring the policy body under 500 words.
- **Problem 3:** Removed Enforcement item 4. The approval requirement appears only in Permitted Uses.
- **Problem 4:** Added outside counsel's DPA finding as a motivating fact in Prohibited Uses item 2.
- **Problem 5:** Removed Scope item 3. The disabled Slack AI features required no policy rule.
- **Problem 6:** Removed Permitted Uses item 3. Budget allocation and future tool approval describe a process not enforceable through existing controls.
- **Problem 7:** Renamed Prohibited Uses item 3 header to remove the undefined "IP review" label.

---

# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables. "Customer data" means any PII, financial data, database schemas, or configuration files that identify or are derived from customer environments.
2. GitHub Copilot Business is the sole approved AI tool. The 80 licensed seats are allocated to engineering roles. Employees without an assigned seat have no approved AI tool.
3. Survey data shows 45% of sales staff are currently using AI tools for email drafting. No AI tool is approved for sales use. Sales staff are covered by the prohibitions below.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, test generation, and documentation on files that contain no customer data.
2. All AI-generated code and written content must receive manager or pull request reviewer approval before merge or external delivery, using existing pull request workflows and email approval chains.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer data into any AI service is prohibited. *(Motivating facts: Incident #1, engineer pasted customer database schema into ChatGPT; SOC2 Type II certification requirements; GDPR obligations; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses for any work-related task is prohibited. *(Motivating facts: Incident #2, AI-generated sales text contained verbatim competitor copyrighted copy; Incident #3, AI-generated code contained a GPL license header; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms.)*
3. **No AI-generated content merged or delivered containing third-party IP.** Pull request reviewers must reject code containing third-party license headers or GPL markers. Managers must reject external communications containing verbatim third-party copyrighted material. *(Motivating facts: Incident #2 verbatim copyrighted copy; Incident #3 GPL header in committed code; outside counsel finding that AI-generated code may not be copyrightable.)*

---

## Enforcement

1. Violations of Prohibited Uses item 1 result in immediate disciplinary action up to and including termination, and are reported to Legal for assessment of DPA, GDPR, and FedRAMP impact.
2. Violations of Prohibited Uses item 2 result in disciplinary review; repeated violations result in termination.
3. Violations of Prohibited Uses item 3 require reversion or withholding of the affected content and disciplinary review of both the submitting employee and the approving reviewer; repeated violations result in termination.