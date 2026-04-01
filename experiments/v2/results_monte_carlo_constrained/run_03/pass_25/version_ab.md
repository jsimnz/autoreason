**TO:** All Employees, Contractors, and Interns
**FROM:** [CEO Name]
**DATE:** [Date]
**SUBJECT:** AI Tool Usage Policy — Effective Immediately

---

## Scope

1. Applies to all employees, contractors, and interns across all functions, effective immediately.
2. Each employee is responsible for confirming a tool is approved under this policy before using it for any work task.

## Permitted Uses

1. **GitHub Copilot Business** (80 licensed seats, allocated and managed by Engineering leadership) is approved for code suggestions, boilerplate generation, and test writing. Use is restricted to tasks that do not involve customer PII or financial data. *(Outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms; SOC2 Type II, GDPR, and pending FedRAMP authorization require demonstrable data control.)*
2. Engineers without an allocated Copilot seat have no approved AI coding tool and must complete work without AI assistance until a seat is allocated to them by Engineering leadership.
3. Additional AI tools require written approval from Engineering leadership before use; no unevaluated tool may be used for any work task pending that approval.

## Prohibited Uses

1. **No customer data in any AI service.** Inputting customer PII, financial data, or customer-identifiable information into any AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms; SOC2 Type II, GDPR, and pending FedRAMP authorization require demonstrable data control.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text in outbound communications requires prior written manager approval confirming that the content is accurate, original, and free of third-party IP before transmission. *(Incident 2: sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy; outside counsel finding that AI-generated content may embed third-party IP.)*
3. **No AI-generated code merged without license review.** A PR containing AI-generated code may not be approved unless the reviewer confirms in the PR record that no third-party license headers or GPL-encumbered content are present. *(Incident 3: intern committed AI-generated code carrying a GPL license header; outside counsel finding that AI-generated code may carry embedded license terms and may not be copyrightable.)*
4. **No unapproved AI tools.** Using any AI service not approved under Permitted Uses for work tasks is prohibited. *(Outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms; Incidents 1 and 2 demonstrate use of unapproved third-party AI services.)*
5. **No enabling of disabled Slack AI features.** Enabling or circumventing disabled Slack AI features is prohibited. *(Company Slack AI features are disabled to prevent uncontrolled data transmission to third-party AI services, which would likely violate existing DPA terms and undermine SOC2 Type II, GDPR, and FedRAMP obligations.)*

## Enforcement

1. All violations are documented in the violating employee's HR file and subject to disciplinary action up to termination.
2. Violation of Prohibition 1 triggers immediate escalation to Security and Legal for breach assessment under SOC2 Type II, GDPR, and FedRAMP authorization obligations.
3. Violation of Prohibition 2 is escalated to Legal for assessment of IP liability under outside counsel's copyright finding.
4. Violation of Prohibition 3 requires the merged commit to be reverted immediately pending Legal review of license exposure.
5. Violation of Prohibitions 4 or 5 triggers review by Security to assess whether customer data or confidential information was transmitted, followed by escalation to Legal if transmission is confirmed.
6. Repeated or willful violations of any prohibition are grounds for immediate termination.