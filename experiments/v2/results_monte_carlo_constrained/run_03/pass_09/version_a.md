**TO:** All Employees, Contractors, and Interns
**FROM:** Office of the CEO
**DATE:** [Date]
**SUBJECT:** AI Tool Usage Policy — Effective Immediately

---

# AI Tool Usage Policy

## Scope

1. Applies to: all employees, contractors, and interns, all functions, effective immediately.
2. Covered activities: any use of AI tools for work-related tasks — coding, writing, data analysis, and customer communications.
3. Covered data: all customer PII, financial data, database schemas, and any customer-identifiable information.

## Permitted Uses

1. **Approved tool:** GitHub Copilot Business only. Engineering leadership manages the 80 licensed seats.
2. **Authorized use:** Seat holders may use GitHub Copilot for code suggestions, boilerplate generation, and test writing on tasks that do not involve customer data.
3. **All other AI tools:** Prohibited unless prior written approval is obtained from the CTO and Legal and documented before use begins. Unauthorized use of any other tool is enforced under Prohibited Use 5 below.

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, database schemas, or any customer-identifiable information into any non-approved AI service is prohibited. *(Motivating facts: Incident 1 — engineer pasted a customer database schema into ChatGPT; outside counsel finding that this likely violates existing DPA terms; SOC2 Type II certification, GDPR obligations, and pending FedRAMP authorization.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be transmitted to customers or prospects until the sender's manager has reviewed it for accuracy, originality, and legal compliance and has recorded that approval in the relevant email thread or CRM record. *(Motivating fact: Incident 2 — sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code committed without license review.** Code produced by AI tools may not be committed without the pull request reviewer confirming in the pull request record that no third-party license headers or GPL-encumbered content are present. *(Motivating facts: Incident 3 — intern committed code containing a GPL license header from AI training data; outside counsel finding that AI-generated code may not be copyrightable.)*
4. **Slack AI features must remain disabled.** Enabling or circumventing the disabled AI features in company Slack is prohibited. *(Motivating fact: Company Slack is provisioned with AI features disabled.)*
5. **No unapproved AI tools.** Accessing or installing non-approved AI services via company devices, accounts, or networks without documented CTO and Legal approval is prohibited. *(Motivating facts: GitHub Copilot Business is the only approved tool; unapproved tools have not been assessed for DPA, SOC2, GDPR, or FedRAMP compliance.)*

## Enforcement

1. Violations involving customer data, copyright, or license exposure are escalated immediately to the Security and Legal teams for breach assessment.
2. Engineering leadership reverts any pull request merged without the required license confirmation and holds it pending completed review.
3. Managers whose direct reports transmit unapproved AI-generated external communications log the incident in the CRM record and notify Legal within 24 hours.
4. Engineering leadership revokes GitHub Copilot seat access for any seat holder found in violation of this policy.
5. A first violation results in a written warning and mandatory manager review. A second violation of any provision results in termination.