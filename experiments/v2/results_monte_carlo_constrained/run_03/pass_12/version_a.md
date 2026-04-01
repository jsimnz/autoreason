**TO:** All Employees, Contractors, and Interns
**FROM:** Office of the CEO
**DATE:** [Date]
**SUBJECT:** AI Tool Usage Policy — Effective Immediately

---

# AI Tool Usage Policy

## Scope

1. Applies to all employees, contractors, and interns across all functions, effective immediately.
2. Covers any use of AI tools for work-related tasks including coding, writing, data analysis, and customer communications.
3. Covers all customer PII, financial data, and database schemas, whether held directly or processed on behalf of EU customers under GDPR obligations.

## Permitted Uses

1. **Approved tool:** GitHub Copilot Business only. Engineering leadership manages the 80 licensed seats.
2. **Authorized use:** Assigned seat holders may use GitHub Copilot for code suggestions, boilerplate generation, and test writing.
3. **Engineers without an assigned seat** are subject to Prohibited Use 5 and may not use any AI coding tool until a seat is assigned or an alternative tool receives documented CTO and Legal approval.
4. **Tool expansion:** Requests for additional AI tools require written approval from the CTO and Legal before use begins.

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or customer-identifiable information (such as a customer's database schema) into any non-approved AI service is prohibited. *(Incident 1 — engineer pasted a customer database schema into ChatGPT; outside counsel finding that doing so violates existing DPA terms; SOC2 Type II certification; GDPR obligations for EU customers.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects unless the sender's manager confirms review for accuracy, originality, and legal compliance in the same thread before sending. *(Incident 2 — sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code committed without license review.** Code produced by AI tools may not be committed unless the pull request reviewer confirms in the PR record that no third-party license headers or GPL-encumbered content are present. *(Incident 3 — intern committed code containing a GPL license header; outside counsel finding that AI-generated code may not be copyrightable.)*
4. **Slack AI features must remain disabled.** Enabling or circumventing disabled AI features in company Slack is prohibited. *(Doing so routes data through third-party AI services, violating DPA terms, SOC2 controls, and jeopardizing pending FedRAMP authorization.)*
5. **No unapproved AI tools.** Using non-approved AI services via company devices, accounts, or networks without documented CTO and Legal approval is prohibited. *(GitHub Copilot Business is the only assessed tool; unapproved tools have not been reviewed for DPA, SOC2, GDPR, or FedRAMP compliance.)*

## Enforcement

1. Violations involving customer data or DPA exposure (Prohibited Uses 1, 4) are escalated immediately to Security and Legal for breach assessment.
2. PR reviewers who identify AI-generated code lacking required license confirmation block the merge and escalate to engineering leadership, who log the incident before any merge proceeds. If a non-compliant merge has already occurred, engineering leadership reverts it as a remediation action independent of the disciplinary track in item 5. *(Prohibited Use 3)*
3. Managers whose direct reports trigger Prohibited Use 2 notify Legal promptly and document the incident in the employee's HR file.
4. Managers who identify use of unapproved AI tools (Prohibited Use 5) or Slack AI circumvention (Prohibited Use 4) revoke device or network access to the service and notify Security and Legal.
5. A first violation results in a written warning documented in the employee's HR file. A second violation results in termination. For violations of Prohibited Use 3, GitHub Copilot seat access is also revoked upon a second violation.