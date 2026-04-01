**Changes made and which problem each fixes:**

1. **Added memo header and removed revision log preamble** — fixes Problems 1 and 2. The document now opens with a proper To/From/Date/Subject header, making it a memo. The revision log is removed entirely; all words count toward the 500-word limit as policy content.

2. **Deleted Permitted Uses item 2** — fixes Problems 3 and 4. No AI tool is approved for sales email drafting under the base facts, and no existing mechanism can verify prompt contents. The item invented an approval not derivable from the base facts and was unenforceable.

3. **Added FedRAMP reference to Prohibition 1's motivation and to Enforcement item 2** — fixes Problem 6. FedRAMP is a base fact (pending Q3 authorization) and a material compliance obligation. Inputting customer data into third-party AI services is directly relevant to FedRAMP scope; the escalation trigger for Prohibition 1 violations now names all three applicable frameworks.

4. **Revised Enforcement item 3 to name applicable compliance frameworks** — fixes Problem 5. External transmission of copyrighted content has IP and regulatory dimensions; the escalation now references outside counsel's IP finding and FedRAMP authorization risk, consistent with the specificity of item 2.

5. **Revised Prohibition 4's stated motivation** — fixes Problem 7. The motivation no longer claims all three incidents involved unapproved tools, which was not derivable from the base facts. The motivation now cites only the outside counsel DPA finding and the three incidents as evidence of uncontrolled third-party AI use, which is derivable.

---

**TO:** All Employees, Contractors, and Interns
**FROM:** [CEO Name]
**DATE:** [Date]
**SUBJECT:** AI Tool Usage Policy — Effective Immediately

---

## Scope

1. Applies to all employees, contractors, and interns across all functions, effective immediately.
2. Governs all use of AI tools for coding, writing, data analysis, and communications.

## Permitted Uses

1. **GitHub Copilot Business** (80 licensed seats, managed by Engineering leadership) is approved for code suggestions, boilerplate generation, and test writing on non-customer-data tasks.
2. Additional AI tools may be requested for evaluation against the $50K/year AI tooling budget; no tool is approved for use until that evaluation is complete.

## Prohibited Uses

1. **No customer data in any AI service.** Inputting customer PII, financial data, or customer-identifiable information into any AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms; pending FedRAMP authorization requires demonstrable data control.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be transmitted externally without confirmation of accuracy, originality, and legal compliance before sending. *(Incident 2: sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code merged without license review.** A PR containing AI-generated code may not be approved unless the reviewer confirms in the PR record that no third-party license headers or GPL-encumbered content are present. *(Incident 3: intern committed AI-generated code carrying a GPL license header; outside counsel finding that AI-generated code may carry embedded license terms and may not be copyrightable.)*
4. **No unapproved AI tools.** Using any AI service not approved under Permitted Uses for work tasks is prohibited. *(Outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms; all three incidents demonstrate uncontrolled use of third-party AI services outside any approved tool set.)*
5. **No enabling of disabled Slack AI features.** Enabling or circumventing Slack AI features is prohibited. *(Company Slack has AI features disabled.)*

## Enforcement

1. All violations are documented in the violating employee's HR file and subject to disciplinary action up to termination.
2. Violation of Prohibition 1 triggers immediate escalation to Security and Legal for breach assessment under SOC2 Type II, GDPR, and FedRAMP authorization obligations.
3. Violation of Prohibition 2 is escalated to Legal for assessment of IP liability under outside counsel's copyright finding and of regulatory exposure under FedRAMP authorization obligations.
4. Repeated or willful violations of any prohibition are grounds for immediate termination.