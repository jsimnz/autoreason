**Changes made and which problems they fix:**

- **Problem 1 & 2 (non-policy preamble and word count):** Removed all revision commentary. The policy memo is the complete deliverable.
- **Problem 4 & 5 (invented reporting chain and 48-hour deadline):** Removed the specific reporting chain to "manager and Legal" and the "48 hours" deadline. Enforcement now references only existing access controls and review processes derivable from the base facts (pull request review, disciplinary action, employment conditions).
- **Problem 6 (Prohibition 4 inconsistent with Prohibition 2):** Rewrote Prohibition 4 to explicitly scope it to GitHub Copilot output only, making it consistent with Prohibition 2's ban on all other tools.
- **Problem 7 (Prohibition 3 burden on reviewers, not committers):** Rewrote Prohibition 3 so the primary obligation falls on the employee submitting the pull request, with reviewers as a secondary check.
- **Problem 8 ("termination review" undefined):** Replaced "escalate to termination review" with "up to and including termination," which is a standard employment condition requiring no invented process.
- **Problem 3 (Permitted Uses single run-on item):** Split the single Permitted Uses item into two discrete numbered items separating the approved use cases from the conditional restriction.

---

# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables.
2. GitHub Copilot Business is the sole approved AI tool, with 80 seats allocated to engineers and managed by the company.
3. No other AI tool is approved for any work-related task by any employee.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) may be used for code completion, test generation, and documentation.
2. GitHub Copilot Business prompts and accepted suggestions must not include customer PII, financial data, or database schemas.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer PII, financial data, or database schemas into any AI service is prohibited. *(Motivating facts: Incident #1 schema exposure; outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses for any work-related task is prohibited, including AI tools used for sales email drafting. *(Motivating facts: Incident #2 verbatim copyrighted copy in AI-drafted sales email; outside counsel DPA violation flag; pending FedRAMP authorization.)*
3. **No AI-generated code submitted without license review.** The employee submitting a pull request must confirm no third-party license headers or GPL markers are present; pull request reviewers must reject any submission lacking that confirmation. *(Motivating facts: Incident #3 GPL header commit; outside counsel copyright non-ownership flag.)*
4. **No GitHub Copilot output distributed externally without Legal sign-off.** Any externally distributed content that includes GitHub Copilot output requires Legal review before distribution. *(Motivating fact: Incident #2 verbatim competitor copyrighted copy; outside counsel copyright non-ownership flag.)*
5. **Slack AI features must remain disabled.** No employee may enable or request enablement of Slack AI features. *(Motivating fact: Outside counsel DPA violation flag applies to any AI service processing company or customer data.)*

---

## Enforcement

1. Violations of Prohibited Uses items 1–2 are security incidents and are subject to immediate disciplinary action for the responsible employee, up to and including termination.
2. Violations of Prohibited Uses items 3–5 are subject to disciplinary action for the responsible employee, up to and including termination.
3. Pull request reviewers who approve merges containing unlicensed AI-generated code without confirming compliance share accountability for the violation and are subject to disciplinary action.
4. Compliance with this policy is a condition of employment.