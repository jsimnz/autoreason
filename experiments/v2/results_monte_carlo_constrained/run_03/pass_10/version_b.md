I'll address each problem, then produce the revised document.

**Changes made:**

- **Problem 1:** Removed the entire "Changes made and problems fixed" preamble.
- **Problem 2:** Tightened language throughout to bring the policy body under 500 words; cut redundant phrases and compressed motivating-fact citations.
- **Problem 3:** Restructured Enforcement so item 2 (revert PR) is a remediation action, not a disciplinary consequence, making it compatible with the graduated discipline in item 4. Seat revocation is now explicitly the consequence of a *second* engineering violation, consistent with item 4's termination tier.
- **Problem 4:** Replaced the email-thread approval mechanism with a requirement that the manager send the communication from their own account on the employee's behalf, which is an enforceable sequencing gate using existing email access controls — the employee cannot send without manager action.
- **Problem 5:** Removed "database schemas" as a standalone protected data category in Scope. Retained the reference in Prohibited Use 1 as "customer-identifiable information such as database schemas," accurately reflecting that the incident involved a *customer's* schema, not schemas generally.
- **Problem 6:** Removed the customer-data restriction from Permitted Use 2; it is fully covered by Prohibited Use 1.

---

**TO:** All Employees, Contractors, and Interns
**FROM:** Office of the CEO
**DATE:** [Date]
**SUBJECT:** AI Tool Usage Policy — Effective Immediately

---

# AI Tool Usage Policy

## Scope

1. Applies to all employees, contractors, and interns across all functions, effective immediately.
2. Covers any use of AI tools for work-related tasks including coding, writing, data analysis, and customer communications.
3. Covers all customer PII and financial data, and any customer-identifiable information handled by the company.
4. Engineering (73% of whom already use AI coding assistants) and sales (45% of whom already use AI for drafting) are explicitly included.

## Permitted Uses

1. **Approved tool:** GitHub Copilot Business only. Engineering leadership manages the 80 licensed seats.
2. **Authorized use:** Seat holders may use GitHub Copilot for code suggestions, boilerplate generation, and test writing.
3. **Tool expansion:** Requests for additional AI tools require written approval from the CTO and Legal before use begins. Approved tools are funded from the $50K annual AI tooling budget.

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or customer-identifiable information (such as a customer's database schema) into any non-approved AI service is prohibited. *(Incident 1; outside counsel finding that doing so likely violates existing DPA terms; SOC2 Type II obligations; GDPR obligations for EU customers.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects unless the sender's manager sends the communication directly from their own account on the employee's behalf, confirming review for accuracy, originality, and legal compliance. *(Incident 2 — sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code committed without license review.** Code produced by AI tools may not be committed unless the pull request reviewer confirms in the PR record that no third-party license headers or GPL-encumbered content are present. *(Incident 3 — intern committed code containing a GPL license header; outside counsel finding that AI-generated code may not be copyrightable.)*
4. **Slack AI features must remain disabled.** Enabling or circumventing disabled AI features in company Slack is prohibited. *(Enabling these features would route data through third-party AI services, likely violating DPA terms, SOC2 controls, and jeopardizing pending FedRAMP authorization.)*
5. **No unapproved AI tools.** Using non-approved AI services via company devices, accounts, or networks without documented CTO and Legal approval is prohibited. *(GitHub Copilot Business is the only assessed tool; unapproved tools have not been reviewed for DPA, SOC2, GDPR, or FedRAMP compliance.)*

## Enforcement

1. Violations involving customer data, copyright, or license exposure are escalated immediately to Security and Legal for breach assessment.
2. Engineering leadership reverts any PR merged without required license confirmation. This revert is a remediation action independent of the disciplinary track below.
3. Managers whose direct reports trigger Prohibited Use 2 notify Legal within 24 hours and document the incident in the employee's HR file.
4. A first violation results in a written warning in the employee's HR file. A second violation results in termination. For engineering violations involving unlicensed code, GitHub Copilot seat access is also revoked upon the second violation.