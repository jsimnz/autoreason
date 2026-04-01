# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all employees on company systems or when handling company data or deliverables.
2. "Customer data" means any PII, financial data, database schemas, or configuration files identifying or derived from customer environments.
3. GitHub Copilot Business (80 licensed seats, allocated to engineering roles) is the sole approved AI tool. No additional tool may be purchased or used for work-related tasks without prior written approval from the CEO and Legal.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, test generation, and documentation on files containing no customer data.
2. Sales staff have no currently allocated AI tool seats. Sales staff assigned a seat under a future CEO- and Legal-approved tool may use it solely for internal drafting workflows, subject to all prohibitions in this policy.
3. All AI-generated code and content must receive manager or pull request reviewer approval before merge or external delivery, using existing pull request workflows and email approval chains.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer data into any AI service is prohibited. *(Motivating facts: Incident #1 — engineer pasted customer database schema into ChatGPT; SOC2 Type II certification; GDPR obligations; pending FedRAMP authorization; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Scope item 3 for work-related tasks is prohibited. *(Motivating facts: Outside counsel DPA violation finding; unapproved tools lack the enterprise data controls present in GitHub Copilot Business; 73% of engineers and 45% of sales already using unapproved tools informally.)*
3. **No third-party IP in merged or delivered content.** Reviewers must reject code containing third-party license headers or GPL markers. Managers must reject external communications containing verbatim third-party copyrighted material. *(Motivating facts: Incident #2 — AI-generated sales copy contained verbatim competitor copyrighted text; Incident #3 — AI-generated code contained a GPL license header.)*
4. **No delivery of AI-generated work product without human authorship review.** All AI-generated code and content must be substantively reviewed and attested by the submitting employee before delivery or merge. *(Motivating fact: Outside counsel finding that AI-generated code may not be copyrightable, creating company IP ownership risk in all AI-generated output.)*

---

## Enforcement

1. Violations of Prohibition 1 result in immediate disciplinary action up to and including termination and are reported to Legal for DPA, GDPR, and FedRAMP impact assessment.
2. Violations of Prohibition 2 result in a formal written warning upon identification. A second violation within 12 months results in termination.
3. Violations of Prohibition 3 or 4 require reversion or withholding of affected content and disciplinary review of both the submitting employee and the approving reviewer. A second violation within 12 months by either party results in termination.
4. Unauthorized procurement of AI tools in violation of Scope item 3 results in immediate revocation of purchasing authority and disciplinary review.