**TO:** All Employees, Contractors, and Interns
**FROM:** Office of the CEO
**DATE:** [Date]
**SUBJECT:** AI Tool Usage Policy — Effective Immediately

---

# AI Tool Usage Policy

## Scope

1. This policy applies to all employees, contractors, and interns across all functions, effective immediately upon issuance.
2. This policy governs any use of AI tools for work-related tasks, including coding, writing, data analysis, and customer communications.
3. This policy supersedes all prior informal AI tool usage, for which no official policy previously existed.

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI tool; Engineering leadership manages allocation of the 80 licensed seats.
2. Seat holders may use GitHub Copilot for code suggestions, boilerplate generation, and test writing on tasks that do not involve customer data.
3. Use of any other AI tool for work-related tasks requires prior written approval from the CTO and Legal, documented before any use begins.

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, database schemas, or any customer-identifiable information into any non-approved AI service is prohibited. *(Motivating facts: Incident 1 — engineer pasted a customer database schema into ChatGPT; outside counsel finding that this likely violates existing DPA terms; SOC2 Type II certification, GDPR obligations, and pending FedRAMP authorization.)*
2. **No AI-generated content in external communications without documented manager approval.** AI-generated text may not be sent to customers or prospects until the sender's manager has reviewed it for accuracy, originality, and legal compliance and has recorded that approval in the relevant email thread or CRM record before transmission. *(Motivating fact: Incident 2 — sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code committed without license review.** Code produced by AI tools may not be committed without the pull request reviewer confirming in the pull request record that no third-party license headers or GPL-encumbered content are present. *(Motivating facts: Incident 3 — intern committed code containing a GPL license header from AI training data; outside counsel finding that AI-generated code may not be copyrightable.)*
4. **Slack AI features must remain disabled.** Enabling or circumventing the disabled AI features in company Slack is prohibited. *(Motivating facts: Company Slack is provisioned with AI features disabled; enabling those features would introduce an unapproved AI service with unassessed DPA, SOC2, GDPR, and FedRAMP compliance exposure.)*
5. **No unapproved AI tools on company systems.** Accessing or installing non-approved AI services via company devices, accounts, or networks is prohibited. *(Motivating facts: GitHub Copilot Business is the only approved tool; unapproved tools have not been assessed for DPA, SOC2, GDPR, or FedRAMP compliance.)*

## Enforcement

1. Violations involving customer data, copyright, or license exposure are escalated immediately to the Security and Legal teams for breach assessment.
2. Engineering leadership reverts any pull request merged without the required license confirmation and holds it pending completed review.
3. Managers whose direct reports transmit unapproved AI-generated external communications are required to log the incident in the CRM record and notify Legal within 24 hours.
4. First violations result in a written warning and mandatory manager review; repeated violations result in disciplinary action up to and including termination.
5. Engineering leadership revokes GitHub Copilot seat access for any seat holder found in violation of this policy.