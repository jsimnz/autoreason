I'll address each problem in turn, then present the revised document.

**Changes made and which problems they fix:**

- **Problem 1 (word count):** Tightened language throughout; removed redundant phrases and consolidated items to get under 500 words.
- **Problem 2 (Scope items not grounded in base facts; "condition of employment" misplaced):** Removed the "prior use does not establish precedent" item (no base fact grounds it). Moved "condition of employment" to Enforcement. Replaced with a scoping item grounded in the survey data and employee breakdown.
- **Problem 3 (Slack AI motivation):** Changed the motivating fact for the Slack prohibition to reference the current company configuration (a base fact) and the DPA flag as it applies to the broader category of unapproved AI features accessing company data, rather than claiming a specific Slack DPA concern not in the base facts. Actually, since no DPA concern for Slack specifically exists in the base facts, the prohibition is motivated solely by the existing company configuration and the unapproved-tool rule — cited accordingly.
- **Problem 4 (unenforceable sales communication requirement):** Moved the human-review requirement for AI-drafted communications into Enforcement, where it is tied to Sales Managers' existing review responsibilities (grounded only in what is derivable — removed the invented one-on-one process per Problem 6).
- **Problem 5 (circular Copilot assertion):** Removed the claim that Copilot "does not receive customer PII." The prohibition in Prohibited Uses already bars inputting customer data into any AI tool; no separate assertion needed.
- **Problem 6 (invented Sales Manager review process):** Removed the specific claim about one-on-ones and deal reviews. Enforcement now states Sales Managers are responsible for reviewing AI-assisted outbound communications as part of their existing managerial oversight, without inventing a specific process.
- **Problem 7 (invented PR templates):** Replaced with a requirement that Engineering Leads verify AI-code review during existing monthly code review cycles, which is grounded in an existing process referenced in the original Enforcement section.
- **Problem 8 (survey figures unused):** Added the 73%/45% survey figures in Scope to establish why the policy is needed and its immediate applicability.
- **Problem 9 (employee breakdown and seat gap):** Added a Scope item noting that 80 Copilot seats are available for 120 engineers; Engineering Ops manages prioritization of seat allocation.

---

# AI Tool Usage Policy
**Effective Date:** [Date] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools—including code assistants, writing tools, and generative AI services—by all employees across all departments (120 engineers, 30 sales, 50 other) on company systems or when handling company data or deliverables.
2. An informal survey found 73% of engineers and 45% of sales staff already use AI tools; this policy applies immediately to all current and future use.
3. GitHub Copilot Business is licensed for 80 of 120 engineers; Engineering Ops manages seat allocation and prioritization for the remaining engineers without seats.

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

1. Violations of Prohibited Use items 1–2 are reportable security incidents. Employees must self-report to Security within 24 hours; managers must escalate to CISO within 48 hours. Failure to self-report is itself a violation.
2. Sales Managers are responsible for verifying that AI-assisted outbound communications have been reviewed and edited by the authoring employee before external distribution, using their existing managerial oversight of direct reports.
3. Engineering Leads verify AI-generated code has been reviewed for license markers during existing monthly code review cycles.
4. Compliance with this policy is a condition of employment. First violations result in mandatory retraining and a written warning. Repeat or willful violations proceed under the standard disciplinary process, up to and including termination.