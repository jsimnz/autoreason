# AI Tool Usage Policy

## Scope

1. This policy applies to all employees, contractors, and interns across all functions, effective immediately upon issuance.
2. This policy governs any use of AI tools for work-related tasks, including coding, writing, data analysis, and customer communications.
3. An informal survey found 73% of engineers and 45% of sales staff are already using AI tools; this policy supersedes all prior informal practice and requires immediate cessation of any use not permitted below.

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI tool. The company holds 80 licensed seats within the $50K annual AI tooling budget; Engineering leadership manages seat allocation.
2. Seat holders may use GitHub Copilot for code suggestions, boilerplate generation, and test writing.
3. No other AI tool is approved for any function. Requests for additional tools require written approval from the CTO and Legal before any use begins.

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, database schemas, or any customer-identifiable information into any non-approved AI service is prohibited. *(Motivating facts: Incident 1 — engineer pasted customer database schema into ChatGPT; outside counsel finding that this likely violates existing DPA terms; SOC2 Type II and GDPR obligations covering customer PII and financial data.)*
2. **No AI-generated content in external communications without review.** AI-generated text may not be sent to customers or prospects without the sender's manager reviewing and approving it for accuracy, originality, and legal compliance before transmission. *(Motivating fact: Incident 2 — sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code committed without license review.** Code produced by AI tools may not be committed without the pull request reviewer confirming in the pull request record that no third-party license headers or GPL-encumbered content are present. *(Motivating facts: Incident 3 — intern committed code containing a GPL license header from AI training data; outside counsel finding that AI-generated code may not be copyrightable.)*
4. **Slack AI features must remain disabled.** Enabling or circumventing the disabled AI features in company Slack is prohibited. *(Motivating facts: Company Slack is provisioned with AI features disabled; outside counsel finding that inputting data into non-approved third-party AI services likely violates existing DPA terms.)*
5. **No unapproved AI tools on company systems.** Accessing or installing non-approved AI services via company devices, accounts, or networks is prohibited. *(Motivating facts: GitHub Copilot Business is the only approved tool; outside counsel finding that unapproved third-party AI services likely violate existing DPA terms.)*

## Enforcement

1. Violations involving customer data, copyright, or license exposure are escalated immediately to the Security and Legal teams for breach assessment.
2. Pull requests merged without the required license confirmation are reverted pending a completed license review.
3. First violations result in a written warning and mandatory manager review. Repeated violations result in disciplinary action up to and including termination.
4. Engineering leadership revokes GitHub Copilot seat access for any seat holder found in violation of this policy.