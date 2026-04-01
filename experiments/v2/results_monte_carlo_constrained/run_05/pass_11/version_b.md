**Changes made and which problems they fix:**

- **Problem 1 & 2:** Removed revision commentary from the deliverable entirely.
- **Problem 3:** Removed Scope item 3 (redundant restatement of items 1 and 2).
- **Problem 4:** Moved the PII/financial data restriction from Permitted Uses into Prohibited Uses as a new numbered prohibition.
- **Problem 5:** Rewrote Prohibition 5 (Slack AI) to cite only the stated base fact: Slack AI features are already disabled per company configuration, and this policy codifies that state.
- **Problem 6:** Removed the "security incident" classification from Enforcement item 1, replacing it with direct disciplinary consequence that operates through existing employment conditions without implying an undefined response process.
- **Problem 7:** Rewrote Prohibition 4's motivating fact to cite only outside counsel's copyright non-ownership flag, which applies to GitHub Copilot output, removing the misattributed Incident #2 reference.

---

# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables.
2. GitHub Copilot Business is the sole approved AI tool, with 80 seats allocated to engineers and managed by the company.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) may be used for code completion, test generation, and documentation within the restrictions defined in Prohibited Uses.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer PII, financial data, or database schemas into any AI service is prohibited. *(Motivating facts: Incident #1 schema exposure; outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses for any work-related task is prohibited, including AI tools used for sales email drafting. *(Motivating facts: Incident #2 verbatim copyrighted copy in AI-drafted sales email; outside counsel DPA violation flag; pending FedRAMP authorization.)*
3. **No GitHub Copilot prompts containing protected data.** Prompts submitted to GitHub Copilot must not include customer PII, financial data, or database schemas. *(Motivating facts: Incident #1 schema exposure; outside counsel DPA violation flag.)*
4. **No AI-generated code submitted without license review.** The employee submitting a pull request must confirm no third-party license headers or GPL markers are present; pull request reviewers must reject any submission lacking that confirmation. *(Motivating facts: Incident #3 GPL header commit; outside counsel copyright non-ownership flag.)*
5. **No GitHub Copilot output distributed externally without Legal sign-off.** Any externally distributed content that includes GitHub Copilot output requires Legal review before distribution. *(Motivating fact: Outside counsel copyright non-ownership flag for AI-generated code.)*
6. **Slack AI features must remain disabled.** No employee may enable or request enablement of Slack AI features. *(Motivating fact: Slack AI features are currently disabled by company configuration; this policy codifies that state as a requirement.)*

---

## Enforcement

1. Violations of Prohibited Uses items 1–3 result in immediate disciplinary action for the responsible employee, up to and including termination.
2. Violations of Prohibited Uses items 4–6 are subject to disciplinary action for the responsible employee, up to and including termination.
3. Pull request reviewers who approve merges containing unlicensed AI-generated code without confirming compliance share accountability for the violation and are subject to disciplinary action.
4. Compliance with this policy is a condition of employment.