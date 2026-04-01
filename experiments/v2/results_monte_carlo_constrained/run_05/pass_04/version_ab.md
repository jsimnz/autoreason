# AI Tool Usage Policy
**Effective Date:** [Date] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools—including code assistants, writing tools, and generative AI services—by all employees across all departments (120 engineers, 30 sales, 50 other) on company systems or when handling company data or deliverables.
2. An informal survey found 73% of engineers and 45% of sales staff already use AI tools; this policy applies immediately to all current and future use.
3. GitHub Copilot Business is licensed for 80 of 120 engineers; Engineering Ops manages seat allocation and prioritization for engineers without seats.
4. This policy supersedes all informal practices.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) is the sole approved AI coding assistant. It may be used for code completion, test generation, and documentation on codebases containing no customer PII or financial data.
2. AI-drafted sales and customer communications are permitted subject to the human review requirement in Enforcement item 2.
3. Requests for additional AI tools must be submitted to Legal before use; approved tools are funded from the $50K annual tooling budget.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer PII, financial data, or database schemas into any AI service is prohibited. *(Motivating facts: Incident #1 schema exposure; outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unapproved external AI services.** Using AI tools not listed in Permitted Uses for any work-related task is prohibited. *(Motivating facts: Outside counsel DPA violation flag; pending FedRAMP authorization.)*
3. **No AI-generated code committed without license review.** All AI-generated code requires human review confirming the absence of third-party license headers and GPL markers before merge. *(Motivating facts: Incident #3 GPL header commit; outside counsel copyright non-ownership flag.)*
4. **No AI-generated content distributed externally without IP review.** Sales and marketing content must be checked against source material before external distribution. *(Motivating fact: Incident #2 verbatim competitor copyrighted copy.)*
5. **Slack AI features must not be enabled.** No employee may request or configure re-enablement without CISO and Legal approval. *(Motivating fact: Current company configuration disables these features; re-enablement would constitute use of an unapproved AI service under Prohibited Use item 2.)*

---

## Enforcement

1. Violations of Prohibited Use items 1–2 are reportable security incidents. Employees must self-report to Security within 24 hours; managers must escalate to CISO within 48 hours. Failure to self-report is itself a violation subject to the disciplinary framework in item 4.
2. Sales Managers are responsible for verifying that AI-assisted outbound communications have been reviewed and edited by the authoring employee before external distribution, using their existing managerial oversight of direct reports.
3. Engineering Leads verify AI-generated code has been reviewed for license markers during existing monthly code review cycles. Pull request templates are updated to include a mandatory checkbox: *"No AI-generated code present, OR AI-generated code reviewed for license markers and IP conflicts."*
4. Compliance with this policy is a condition of employment. First violations result in mandatory retraining and a written warning. Repeat or willful violations proceed under the standard disciplinary process, up to and including termination.