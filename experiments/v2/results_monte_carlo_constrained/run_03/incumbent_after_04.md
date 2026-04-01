# AI Tool Usage Policy

## Scope

1. This policy applies to all employees, contractors, and interns across all functions, effective immediately upon issuance.
2. This policy governs any use of AI tools for work-related tasks, including coding, writing, data analysis, and customer communications.
3. Employees currently using any AI tool not approved in this policy for work tasks must cease that use immediately upon issuance of this policy.

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI tool for engineering staff. Use is limited to the 80 licensed seats; Engineering leadership manages seat allocation.
2. Engineers may use GitHub Copilot for code suggestions, boilerplate generation, and test writing.
3. No AI tool is approved for sales staff or any non-engineering function. Requests for additional tools require written approval from the CTO and Legal before any use begins.

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, database schemas, or any customer-identifiable information into any non-approved AI service is prohibited. *(Motivating facts: Incident 1 — engineer pasted customer database schema into ChatGPT; outside counsel finding that this likely violates existing DPA terms; SOC2 Type II and GDPR obligations covering customer PII and financial data.)*
2. **No AI-generated content in external communications without review.** AI-generated text may not be sent to customers or prospects without the sender's manager reviewing and approving it for accuracy, originality, and legal compliance before transmission. *(Motivating fact: Incident 2 — sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code committed without license review.** Code produced by AI tools may not be committed without the pull request reviewer confirming in the pull request record that no third-party license headers or GPL-encumbered content are present. *(Motivating facts: Incident 3 — intern committed code containing a GPL license header sourced from AI training data; outside counsel finding that AI-generated code may not be copyrightable.)*
4. **Slack AI features must remain disabled.** Enabling or circumventing the disabled AI features in company Slack is prohibited. *(Motivating facts: Company Slack is provisioned with AI features disabled; outside counsel finding that inputting data into non-approved third-party AI services likely violates existing DPA terms covering customer PII and financial data.)*
5. **No unapproved AI tools on company systems.** Accessing or installing non-approved AI services via company devices, accounts, or networks is prohibited. *(Motivating facts: GitHub Copilot Business is the only approved tool; outside counsel finding that use of unapproved third-party AI services likely violates existing DPA terms.)*
6. **Sales staff may not use AI tools for email drafting or customer communications.** No AI-generated content may be used in sales outreach or customer-facing communications until a tool is approved per Permitted Uses item 3. *(Motivating facts: 45% of sales staff are already using AI for email drafting with no approved tool in place; Incident 2 — AI-generated sales communication contained verbatim copyrighted content.)*
7. **No AI tool use incompatible with pending FedRAMP authorization.** Until FedRAMP authorization is obtained, no AI tool may be used in any manner inconsistent with the requirements of that pending authorization. *(Motivating fact: FedRAMP authorization is pending with a Q3 target.)*

## Enforcement

1. Violations involving customer data, copyright, or license exposure are escalated immediately to the Security and Legal teams for breach assessment.
2. Pull requests merged without the required license confirmation are reverted pending a completed license review.
3. First violations result in a written warning and mandatory manager review. Repeated violations result in disciplinary action up to and including termination.
4. Engineering leadership revokes GitHub Copilot seat access for any employee found in violation of this policy.