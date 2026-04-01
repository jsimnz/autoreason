# AI Tool Usage Policy

## Scope

1. Applies to all employees, contractors, and interns across all functions, effective immediately.
2. Governs all use of AI tools for coding, writing, data analysis, and communications.

## Permitted Uses

1. **GitHub Copilot Business** (80 licensed seats, managed by Engineering leadership) is approved for code suggestions, boilerplate generation, and test writing on non-customer-data tasks.
2. **Sales staff** may use AI tools for email drafting only when no customer data, competitor content, or unverified claims are included in the submitted prompt or output, and the sender confirms accuracy and originality before transmission.
3. Additional AI tools may be requested through Engineering or department leadership for evaluation against the $50K/year AI tooling budget; no tool is approved for use until that evaluation is complete.

## Prohibited Uses

1. **No customer data in any AI service.** Inputting customer PII, financial data, or customer-identifiable information into any AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be transmitted externally without confirmation of accuracy, originality, and legal compliance before sending. *(Incident 2: sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code merged without license review.** A PR containing AI-generated code may not be approved unless the reviewer confirms in the PR record that no third-party license headers or GPL-encumbered content are present. *(Incident 3: intern committed AI-generated code carrying a GPL license header; outside counsel finding that AI-generated code may carry embedded license terms and may not be copyrightable.)*
4. **No unapproved AI tools.** Using any AI service not approved under Permitted Uses for work tasks is prohibited. *(All three incidents involved tools outside any approved or assessed tool set; outside counsel DPA finding applies to third-party AI services generally.)*
5. **No enabling of disabled Slack AI features.** Enabling or circumventing Slack AI features is prohibited. *(Company Slack has AI features disabled; outside counsel finding that inputting data into third-party AI services likely violates existing DPA terms.)*

## Enforcement

1. All violations are documented in the violating employee's HR file and subject to disciplinary action up to termination.
2. Violation of Prohibition 1 triggers immediate escalation to Security and Legal for breach assessment under SOC2 and GDPR obligations.
3. Violation of Prohibition 2 is escalated to Legal for assessment before any external remediation action is taken.
4. Violation of Prohibition 3 is the accountable responsibility of the employee who committed the code; that employee's HR file is documented accordingly.
5. Repeated or willful violations of any prohibition are grounds for immediate termination.