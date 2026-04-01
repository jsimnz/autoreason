I'll address each problem systematically, then present the revised document.

**Changes made and which problems they fix:**

- **Problem 1 (word count):** Compressed Enforcement to one consolidated item plus per-violation consequences; trimmed parentheticals; removed redundant prose throughout.
- **Problem 2 (Prohibition 4 base fact):** Replaced rationale statement with citation to specific base facts: outside counsel DPA finding and the three incidents, all of which involved unapproved tools.
- **Problem 3 (Prohibition 5 parenthetical):** Replaced circular reasoning with the actual motivating base fact: company decision to disable Slack AI features, combined with the DPA finding and SOC2/GDPR obligations that motivated that decision.
- **Problem 4 (Copilot exempt from customer data prohibition):** Removed the implicit exemption. Prohibition 1 now bars customer data input into any AI service, including Copilot, without carving out an exception not supported by base facts.
- **Problem 5 (unseated engineering staff rule):** Removed the invented rule. Permitted Uses now states only what the base facts support: 80 licensed Copilot seats are available for code tasks.
- **Problem 6 (invented escalation paths):** Replaced specific invented escalation chains with enforcement actions grounded only in existing processes derivable from base facts: PR review process, manager review process, and HR documentation.
- **Problem 7 ($50K budget unused):** Added a Permitted Uses item referencing the $50K budget as the authorization basis for additional tool requests, making the fact active in the policy.
- **Problem 8 (45% sales statistic unused):** Added a Scope item acknowledging the survey finding that 45% of sales staff use AI tools, establishing the factual basis for why sales is explicitly covered.

---

**TO:** All Employees, Contractors, and Interns
**FROM:** Office of the CEO
**DATE:** [Date]
**SUBJECT:** AI Tool Usage Policy — Effective Immediately

---

# AI Tool Usage Policy

## Scope

1. Applies to all employees, contractors, and interns across all functions, effective immediately.
2. Governs all use of AI tools for coding, writing, data analysis, and communications.
3. An internal survey found 73% of engineers and 45% of sales staff already using AI tools; this policy governs all such existing and future use.
4. The company handles customer PII and financial data and holds SOC2 Type II certification, GDPR obligations for EU customers, and a pending FedRAMP authorization targeted for Q3.

## Permitted Uses

1. **GitHub Copilot Business** (80 licensed seats, managed by Engineering leadership) is approved for code suggestions, boilerplate generation, and test writing on non-customer-data tasks.
2. Additional AI tools may be requested through Engineering or department leadership for evaluation against the $50K/year AI tooling budget; no tool is approved for use until that evaluation is complete.

## Prohibited Uses

1. **No customer data in any AI service.** Inputting customer PII, financial data, or customer-identifiable information into any AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms; SOC2 Type II certification; GDPR obligations; pending FedRAMP authorization.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be transmitted externally without manager confirmation of accuracy, originality, and legal compliance, recorded before sending. *(Incident 2: sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code merged without license review.** A PR containing AI-generated code may not be approved unless the reviewer confirms in the PR record that no third-party license headers or GPL-encumbered content are present. *(Incident 3: intern committed AI-generated code carrying a GPL license header; outside counsel finding that AI-generated code may carry embedded license terms and may not be copyrightable.)*
4. **No unapproved AI tools.** Using any AI service not approved under Permitted Use 2 for work tasks is prohibited. *(All three incidents involved use of tools outside any approved or assessed tool set; outside counsel DPA finding applies to third-party AI services generally.)*
5. **No enabling of disabled Slack AI features.** Enabling or circumventing Slack AI features is prohibited. *(Company has disabled Slack AI features; outside counsel DPA finding; SOC2 Type II certification; GDPR obligations for EU customers.)*

## Enforcement

1. Violations are documented in the violating employee's HR file and subject to disciplinary action up to termination.
2. Violation of Prohibition 1 triggers immediate Security and Legal review for breach assessment under SOC2 and GDPR obligations.
3. Violation of Prohibition 3 is the accountable responsibility of the PR reviewer who approved the merge; that reviewer's HR file is documented accordingly.
4. Repeated or willful violations of any prohibition are grounds for immediate termination.