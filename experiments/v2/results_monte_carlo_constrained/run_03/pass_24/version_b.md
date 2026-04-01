**Changes made and which problem each fixes:**

1. **Removed the revision commentary preamble entirely** — fixes Problems 1 and 2. The document now opens directly with the memo header. No prefatory material is present.

2. **Revised Prohibition 2 to require manager sign-off before external transmission** — fixes Problem 4. Manager approval of outbound communications is an existing review process requiring no new tooling. The prohibition is now enforceable through that mechanism.

3. **Removed FedRAMP reference from Enforcement item 3** — fixes Problem 5. No derivable connection exists between transmitting copyrighted copy and FedRAMP authorization risk. The escalation now references only outside counsel's copyright finding.

4. **Revised Prohibition 4's motivation to remove the claim that all three incidents involved unapproved tools** — fixes Problem 3. The motivation now cites only the outside counsel DPA finding and the specific incidents where unapproved tool use is inferable (Incidents 1 and 2), not Incident 3.

5. **Revised Permitted Uses item 2 to name Engineering leadership as the approval authority and require written approval before use** — fixes Problem 6. Engineering leadership is already named as the management authority for the approved tool set; written approval by a named authority using no new tooling is enforceable under existing processes.

6. **Revised Scope item 2 to state a discrete, enforceable obligation** — fixes Problem 7. The item now states that each employee is responsible for knowing which tools are approved before use, which is a concrete individual obligation rather than a descriptive header clause.

---

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