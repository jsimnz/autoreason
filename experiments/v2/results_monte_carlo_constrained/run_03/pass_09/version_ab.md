**TO:** All Employees, Contractors, and Interns
**FROM:** Office of the CEO
**DATE:** [Date]
**SUBJECT:** AI Tool Usage Policy — Effective Immediately

---

# AI Tool Usage Policy

## Scope

1. Applies to all employees, contractors, and interns across all functions, effective immediately.
2. Covers any use of AI tools for work-related tasks: coding, writing, data analysis, and customer communications.
3. Covers all customer PII, financial data, database schemas, and any customer-identifiable information.
4. Engineering (73% of whom already use AI coding assistants) and sales (45% of whom already use AI for drafting) are explicitly included.

## Permitted Uses

1. **Approved tool:** GitHub Copilot Business only. Engineering leadership manages the 80 licensed seats.
2. **Authorized use:** Seat holders may use GitHub Copilot for code suggestions, boilerplate generation, and test writing on tasks that do not involve customer data.
3. **Tool expansion:** Requests for additional AI tools must receive written approval from the CTO and Legal before use begins. Approved tools are funded from the $50K annual AI tooling budget.

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any non-approved AI service is prohibited. *(Incident 1 — engineer pasted a customer database schema into ChatGPT; outside counsel finding this likely violates existing DPA terms; SOC2 Type II obligations; GDPR obligations for EU customers; jeopardizes pending FedRAMP authorization.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects until the sender's manager reviews it for accuracy, originality, and legal compliance and replies in the same email thread confirming approval. *(Incident 2 — sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code committed without license review.** Code produced by AI tools may not be committed unless the pull request reviewer confirms in the PR record that no third-party license headers or GPL-encumbered content are present. *(Incident 3 — intern committed code containing a GPL license header; outside counsel finding that AI-generated code may not be copyrightable.)*
4. **Slack AI features must remain disabled.** Enabling or circumventing disabled AI features in company Slack is prohibited. *(Enabling these features would route data through third-party AI services, likely violating DPA terms, SOC2 controls, and jeopardizing pending FedRAMP authorization.)*
5. **No unapproved AI tools.** Using non-approved AI services via company devices, accounts, or networks without documented CTO and Legal approval is prohibited. *(GitHub Copilot Business is the only assessed tool; unapproved tools have not been reviewed for DPA, SOC2, GDPR, or FedRAMP compliance.)*

## Enforcement

1. Violations involving customer data, copyright, or license exposure are escalated immediately to Security and Legal for breach assessment.
2. Engineering leadership reverts any PR merged without the required license confirmation; upon revert, the seat holder's GitHub Copilot access is also revoked pending review.
3. Managers whose direct reports transmit unapproved AI-generated external communications notify Legal within 24 hours and document the incident in the employee's HR file.
4. A first violation results in a written warning documented in the employee's HR file. A second violation of any provision results in termination.