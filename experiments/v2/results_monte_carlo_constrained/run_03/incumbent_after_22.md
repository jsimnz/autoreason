**Changes made and which problem each fixes:**

1. **Removed the "Changes Made" section entirely** — fixes Problems 1 and 2. It is not policy content and was not requested.

2. **Revised Permitted Uses item 2 to remove the unenforceable conditions on prompt and output content** — fixes Problem 4. No existing review process for sales email drafts is derivable from the base facts. The item now permits the use without conditions that cannot be enforced through existing controls.

3. **Revised Enforcement item 3 to remove the pre-remediation Legal consultation requirement** — fixes Problem 3. No remediation workflow or Legal review gate prior to remediation is derivable from the base facts.

4. **Revised Prohibition 5 to remove the DPA citation as motivation** — fixes Problem 5. The DPA finding addresses third-party AI services; the base facts state only that Slack AI features are disabled, not why. The motivation is now the base fact that the features are disabled.

5. **Deleted Enforcement item 4** — fixes Problems 1 and 6. It restates item 1 without adding distinct enforcement content and consumes word count without substance.

---

# AI Tool Usage Policy

## Scope

1. Applies to all employees, contractors, and interns across all functions, effective immediately.
2. Governs all use of AI tools for coding, writing, data analysis, and communications.

## Permitted Uses

1. **GitHub Copilot Business** (80 licensed seats, managed by Engineering leadership) is approved for code suggestions, boilerplate generation, and test writing on non-customer-data tasks.
2. **Sales staff** may use AI tools for internal email drafting only when no customer data is included in the submitted prompt.
3. Additional AI tools may be requested for evaluation against the $50K/year AI tooling budget; no tool is approved for use until that evaluation is complete.

## Prohibited Uses

1. **No customer data in any AI service.** Inputting customer PII, financial data, or customer-identifiable information into any AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be transmitted externally without confirmation of accuracy, originality, and legal compliance before sending. *(Incident 2: sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code merged without license review.** A PR containing AI-generated code may not be approved unless the reviewer confirms in the PR record that no third-party license headers or GPL-encumbered content are present. *(Incident 3: intern committed AI-generated code carrying a GPL license header; outside counsel finding that AI-generated code may carry embedded license terms and may not be copyrightable.)*
4. **No unapproved AI tools.** Using any AI service not approved under Permitted Uses for work tasks is prohibited. *(All three incidents involved tools outside any approved or assessed tool set; outside counsel DPA finding applies to third-party AI services generally.)*
5. **No enabling of disabled Slack AI features.** Enabling or circumventing Slack AI features is prohibited. *(Company Slack has AI features disabled.)*

## Enforcement

1. All violations are documented in the violating employee's HR file and subject to disciplinary action up to termination.
2. Violation of Prohibition 1 triggers immediate escalation to Security and Legal for breach assessment under SOC2 and GDPR obligations.
3. Violation of Prohibition 2 is escalated to Legal for assessment.
4. Repeated or willful violations of any prohibition are grounds for immediate termination.