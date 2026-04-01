# AI Tool Usage Policy
**Effective Date:** [Date] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools—including code assistants, writing tools, and generative AI services—by all 200 employees on company systems or when handling company data or deliverables.
2. This policy supersedes all informal practices.
3. Compliance with this policy is a condition of employment.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) is the sole approved AI coding assistant; seat assignments are managed by Engineering Ops. Copilot is approved on the basis that it does not receive customer PII or financial data under permitted use conditions.
2. Copilot may be used for code completion, test generation, and documentation on codebases containing no customer PII or financial data.
3. AI-drafted sales and customer communications are permitted only when reviewed, edited, and sent by the authoring employee.
4. Requests for additional AI tools must be submitted to Legal for review before use; the $50K annual tooling budget governs expenditure on approved tools.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer PII, financial data, or database schemas into any AI service is prohibited. *(Motivating facts: Incident #1 schema exposure; outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unapproved external AI services.** Using AI tools not listed in Permitted Uses for any work-related task is prohibited. *(Motivating facts: Outside counsel DPA violation flag; pending FedRAMP authorization.)*
3. **No AI-generated code committed without license review.** All AI-generated code requires human review confirming the absence of third-party license headers and GPL markers before merge. *(Motivating facts: Incident #3 GPL header commit; outside counsel copyright non-ownership flag.)*
4. **No AI-generated content published externally without IP review.** Sales and marketing content must be checked against source material before external distribution. *(Motivating fact: Incident #2 verbatim competitor copyrighted copy.)*
5. **Slack AI features must not be enabled.** No employee may request or configure re-enablement without CISO and Legal approval. *(Motivating fact: Outside counsel DPA violation flag; current company configuration disables these features.)*

---

## Enforcement

1. Violations of Prohibited Use items 1–2 are reportable security incidents. Employees must self-report to Security within 24 hours; managers must escalate to CISO within 48 hours. Failure to self-report is itself a violation subject to the disciplinary framework in item 4.
2. Engineering Leads conduct AI-usage spot audits during existing monthly code review cycles. Sales Managers review outbound communications for AI-usage compliance during existing one-on-one or deal review meetings with direct reports.
3. Pull request templates are updated immediately to include a mandatory checkbox: *"No AI-generated code present, OR AI-generated code reviewed for license markers."*
4. First violations result in mandatory retraining and a documented written warning. Repeat or willful violations proceed under the standard disciplinary process, up to and including termination.

---

**Changes made and problems addressed:**

- **Problem 7 (fifth section) and Problem 1 (word count):** The "Synthesis rationale by dimension" section has been removed entirely. The document now contains exactly four sections, and the word count constraint is met.
- **Problem 6 (Scope item 2 is prose reasoning):** Scope item 2 was shortened to "This policy supersedes all informal practices." — a direct, actionable policy statement rather than a defensive legal argument.
- **Problem 4 (Legal sign-off workflow invented):** Permitted Use item 4 is rewritten to state that requests must be submitted to Legal for review, which is derivable from Legal's established role in the document, without inventing a formal approval workflow not in the base facts. The budget reference is retained as a factual anchor.
- **Problem 2 (verbatim copied text unverifiable):** Prohibited Use item 3 is narrowed to cover only license headers and GPL markers — items detectable through standard code review — removing the claim about "verbatim copied text," which requires tooling not established in the base facts. The enforcement checkbox is updated to match.
- **Problem 3 (sales review lacks specificity):** Enforcement item 2 replaces the unsupported reference to "pipeline review cycles" with "existing one-on-one or deal review meetings with direct reports," which is a standard management practice derivable from the organizational structure without asserting that pipeline reviews already cover AI-usage examination.
- **Problem 5 (Slack AI motivating facts unsupported):** The citation for Prohibited Use item 5 is revised to reference the outside counsel DPA violation flag and the established fact that the company currently has Slack AI features disabled, without attributing SOC2/FedRAMP as the cause of that configuration.