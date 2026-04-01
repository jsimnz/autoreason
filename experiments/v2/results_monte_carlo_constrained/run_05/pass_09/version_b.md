I'll address each problem, then present the revised document.

**Changes made and which problems they fix:**

- **Problem 1 (non-policy preamble):** Removed the entire revision log preamble. The policy memo is the complete deliverable.
- **Problem 2 (word count):** Removing the preamble and tightening language throughout brings the document within 500 words.
- **Problem 3 (Permitted Uses item 2 is an approval process):** Removed the budget/approval-process item from Permitted Uses. The $50K budget fact is not a permitted use and introduced an unenforced process.
- **Problem 4 (Prohibition 4 unenforceable):** Replaced the unenforceable "verify against source material" requirement with a prohibition on distributing AI-assisted content externally without Legal sign-off — enforceable through the existing Legal review process already invoked in Enforcement.
- **Problem 5 (Prohibition 5 motivation fabricated):** Revised the motivating fact citation to state only the DPA risk as the justification; removed the circular reference to current disabled status as a motivating fact.
- **Problem 6 (self-reporting requirement not derivable):** Removed the 24-hour self-reporting rule and the "failure to self-report is itself a violation" language. Enforcement now relies on manager and Legal review, which is derivable from existing organizational structure without inventing new procedures.
- **Problem 7 (Scope item 2 redundant):** Removed Scope item 2. The effective date on the header already establishes applicability timing.

---

# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables.
2. GitHub Copilot Business is the sole approved AI tool; 80 seats are allocated to engineers and managed by the company.
3. No other AI tool is approved for any work-related task by any employee.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) may be used for code completion, test generation, and documentation, provided no customer PII or financial data is included in the prompt or accepted suggestion input.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer PII, financial data, or database schemas into any AI service is prohibited. *(Motivating facts: Incident #1 schema exposure; outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses for any work-related task is prohibited, including AI tools used for sales email drafting. *(Motivating facts: Incident #2 verbatim copyrighted copy in AI-drafted sales email; outside counsel DPA violation flag; pending FedRAMP authorization.)*
3. **No AI-generated code committed without license review.** Pull request reviewers must confirm no third-party license headers or GPL markers are present before merge. *(Motivating facts: Incident #3 GPL header commit; outside counsel copyright non-ownership flag.)*
4. **No AI-assisted content distributed externally without Legal sign-off.** Any externally distributed content that was AI-assisted requires Legal review before distribution. *(Motivating fact: Incident #2 verbatim competitor copyrighted copy.)*
5. **Slack AI features must remain disabled.** No employee may enable or request enablement of Slack AI features. *(Motivating fact: Outside counsel DPA violation flag applies to any AI service processing company or customer data.)*

---

## Enforcement

1. Violations of Prohibited Uses items 1–2 are security incidents. The discovering employee reports to their manager and Legal immediately. Both the responsible employee and their manager are subject to disciplinary action.
2. Violations of Prohibited Uses items 3–5 are reported by the discovering employee or reviewer to their manager and Legal within 48 hours. The responsible employee is subject to disciplinary action; repeated violations escalate to termination review.
3. Pull request reviewers who approve merges containing unlicensed AI-generated code without confirming compliance share accountability for the violation.
4. Compliance with this policy is a condition of employment. Violations are subject to disciplinary action up to and including termination.