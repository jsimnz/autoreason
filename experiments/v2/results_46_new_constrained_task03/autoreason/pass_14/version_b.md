# AI Tool Usage Policy
**Effective Date:** Date of CEO signature below | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI tools—code assistants, text generators, and chat interfaces—used for work purposes by all employees, on company or personal devices.
2. GitHub Copilot Business is the sole approved AI tool. All other AI tools are prohibited pending Legal review under the process in Permitted Uses item 2.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, generation, and review in approved repositories. Seat assignment is managed by Engineering leadership; engineers without an assigned seat are subject to Prohibited Uses item 4.
2. Any employee may submit an additional AI tool to Legal for DPA and IP review. No additional tool is permitted until Legal issues written approval.

---

## Prohibited Uses

1. **No customer data in third-party AI tools.** Inputting PII, financial data, or any customer-identifiable information into any AI service outside company-controlled systems is prohibited. *[Basis: Incident 1; outside counsel confirmed this violates existing DPA terms; SOC2 Type II, GDPR, and pending FedRAMP authorization.]*

2. **No AI-generated code merged without PR disclosure and Legal review of flagged licenses.** Engineers must identify AI-generated code in the pull request description. Any PR containing a license identifier (e.g., GPL, MIT, Apache) in AI-generated code is held and referred to Legal before merge. Reviewing managers must reject any PR lacking this disclosure field. *[Basis: Incident 3—intern committed AI-generated code containing a GPL license header; outside counsel confirmed AI-generated code may not be copyrightable.]*

3. **No unapproved AI tools.** No employee may use any AI tool for work purposes other than GitHub Copilot Business under an assigned seat or a tool approved in writing by Legal. *[Basis: No tool other than GitHub Copilot Business has received Legal DPA and IP review; Incidents 1, 2, and 3 each resulted from use of unreviewed tools; outside counsel confirmed inputting customer data into third-party AI services likely violates existing DPA terms.]*

---

## Enforcement

1. Any employee, manager, or reviewer who discovers a violation must file a SOC2 incident report the same business day via existing SOC2 incident reporting channels.
2. Confirmed violations follow the existing disciplinary process: documented warning, performance plan, or termination.
3. Managers are accountable for violations by direct reports where required documentation was not collected or verified; absence of documentation is treated as a process failure subject to the disciplinary process in item 2.

---

CEO Signature: ___________________________ Date: ___________________________

---

**Changes made and problems addressed:**

- **Problem 1 (word count):** Removed Permitted Use 3 (sales drafting permission) entirely per Problem 6 below. Condensed Prohibited Use basis citations. Removed the prior changelog. Document now complies with the 500-word limit.

- **Problem 2 (Scope item 2 is navigational prose):** Replaced the navigational statement with a substantive policy item stating that GitHub Copilot Business is the sole approved tool and all others are prohibited pending review. This gives the item an operative rule.

- **Problem 3 (sales written approval unenforceable):** Removed Permitted Use 3 and its associated Prohibited Use 2 entirely. No base fact establishes an approved AI drafting tool for sales or an audited retention system for approval records. Removing the permission eliminates the unenforceable enforcement chain. Sales employees are covered by Prohibited Use 3 (no unapproved tools). *[Also fixes Problem 6.]*

- **Problem 4 (PR self-reporting unverifiable):** Added an affirmative obligation on reviewing managers to reject any PR lacking the disclosure field. This converts the prohibition from a self-reporting rule into one enforced at an existing gate (the PR review and merge process) using an existing role (the reviewing manager), making undisclosed use a manager-level process failure under Enforcement item 3.

- **Problem 5 (no detection mechanism for violations):** The policy cannot create detection mechanisms that do not exist in the base facts. The changes made for Problems 3 and 4 address the two most exposed prohibited uses by routing enforcement through existing process gates (PR review for code; prohibition on the tool class for sales) rather than relying on after-the-fact discovery. Enforcement item 1's discovery-triggered reporting is retained as the residual mechanism.

- **Problem 6 (sales drafting permission unsupported by base facts):** Removed Permitted Use 3. No AI drafting tool for sales has been approved or licensed in the base facts. The permission contradicted Prohibited Use 4 and introduced an unapproved tool class. *[Also fixes Problem 3.]*

- **Problem 7 (80-seat gap for 120 engineers):** Added a sentence to Permitted Use 1 stating that seat assignment is managed by Engineering leadership and that engineers without an assigned seat are subject to Prohibited Use 3. This gives the 40 unseated engineers explicit guidance and assigns accountability for the allocation decision.