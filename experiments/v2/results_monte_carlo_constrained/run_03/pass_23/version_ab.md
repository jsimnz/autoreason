# AI Tool Usage Policy

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

---

**Synthesis rationale by dimension:**

- **Memo header:** Version Y's formal To/From/Date/Subject header is adopted. Version X opens directly with a section heading; a policy memo requires a header to be a memo.
- **Permitted Uses item 2 (sales email drafting):** Deleted, following Version Y. Version X retained the item but conditioned it on prompt content verification, which no existing control can enforce. Version Y correctly identified that no sales AI tool is approved under the base facts and removed the item entirely.
- **Prohibition 1 motivation:** Version Y's formulation is adopted. It adds the FedRAMP data-control rationale, which is directly derivable from the base facts and materially strengthens enforceability against a compliance audience.
- **Prohibition 4 motivation:** Version Y's formulation is adopted. Version X's claim that all three incidents involved tools outside any approved set overstates what is derivable; Version Y's phrasing ("demonstrate uncontrolled use") is accurate to the facts.
- **Enforcement items 2 and 3:** Version Y's formulations are adopted. Naming all three applicable compliance frameworks (SOC2, GDPR, FedRAMP) in item 2 is more complete and enforceable. Version Y's item 3 adds FedRAMP exposure to the copyright escalation, which is derivable and relevant.
- **Enforcement item count:** Both versions converge on four enforcement items in the final text; Version X's deleted duplicate item is not restored.