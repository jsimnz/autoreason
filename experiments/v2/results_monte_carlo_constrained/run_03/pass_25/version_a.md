**TO:** All Employees, Contractors, and Interns
**FROM:** [CEO Name]
**DATE:** [Date]
**SUBJECT:** AI Tool Usage Policy — Effective Immediately

---

## Scope

1. Applies to all employees, contractors, and interns across all functions, effective immediately.
2. Each employee is responsible for confirming a tool is approved under this policy before using it for any work task.

## Permitted Uses

1. **GitHub Copilot Business** (80 licensed seats, managed by Engineering leadership) is approved for code suggestions, boilerplate generation, and test writing on non-customer-data tasks.
2. Additional AI tools require written approval from Engineering leadership before use; no unevaluated tool may be used for any work task pending that approval.

## Prohibited Uses

1. **No customer data in any AI service.** Inputting customer PII, financial data, or customer-identifiable information into any AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms; pending FedRAMP authorization requires demonstrable data control.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be transmitted externally without prior written manager approval confirming accuracy, originality, and legal compliance. *(Incident 2: sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code merged without license review.** A PR containing AI-generated code may not be approved unless the reviewer confirms in the PR record that no third-party license headers or GPL-encumbered content are present. *(Incident 3: intern committed AI-generated code carrying a GPL license header; outside counsel finding that AI-generated code may carry embedded license terms and may not be copyrightable.)*
4. **No unapproved AI tools.** Using any AI service not approved under Permitted Uses for work tasks is prohibited. *(Outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms; Incidents 1 and 2 demonstrate use of third-party AI services outside any approved tool set.)*
5. **No enabling of disabled Slack AI features.** Enabling or circumventing Slack AI features is prohibited. *(Company Slack has AI features disabled.)*

## Enforcement

1. All violations are documented in the violating employee's HR file and subject to disciplinary action up to termination.
2. Violation of Prohibition 1 triggers immediate escalation to Security and Legal for breach assessment under SOC2 Type II, GDPR, and FedRAMP authorization obligations.
3. Violation of Prohibition 2 is escalated to Legal for assessment of IP liability under outside counsel's copyright finding.
4. Repeated or willful violations of any prohibition are grounds for immediate termination.

---

**Synthesis rationale by dimension:**

- **Scope item 2:** Version X's formulation ("each employee is responsible for confirming") is a concrete, enforceable individual obligation. Version Y's "governs all use of AI tools for…" is a descriptive header clause, not an obligation. X wins.

- **Permitted Uses item 2:** Version X requires written approval from a named authority (Engineering leadership) before use — enforceable under existing processes with no new tooling. Version Y's formulation ("may be requested for evaluation") is aspirational and names no approval authority. X wins.

- **Prohibition 2 enforceability:** Version X adds "prior written manager approval" as the enforcement mechanism, making the prohibition enforceable through an existing review process. Version Y's "confirmation before sending" names no responsible party and no mechanism. X wins.

- **Prohibition 4 motivation:** Version X cites only Incidents 1 and 2 as demonstrating unapproved tool use, which is inferable from the base facts. Version Y claims all three incidents demonstrate this, which overclaims for Incident 3 (the intern used Copilot, an approved tool). X wins.

- **Enforcement item 2 (FedRAMP):** Both versions include FedRAMP in the Prohibition 1 escalation trigger. This is correct: inputting customer data into third-party services is directly material to FedRAMP authorization. Both agree; retained.

- **Enforcement item 3 (FedRAMP for Prohibition 2):** Version Y adds FedRAMP exposure to the Prohibition 2 escalation. The base facts establish no direct connection between transmitting copyrighted marketing copy and FedRAMP authorization risk. Version X omits this reference correctly. X wins.