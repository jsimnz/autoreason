# AI Tool Usage Policy
**Effective Date:** Date of CEO signature below | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI tools—code assistants, text generators, and chat interfaces—used for work purposes by all employees, on company or personal devices.
2. GitHub Copilot Business is the sole approved AI tool. All other AI tools are prohibited pending Legal review under the process in Permitted Uses item 2.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, generation, and review in approved repositories. Seat assignment is managed by Engineering leadership; engineers without an assigned seat are subject to Prohibited Uses item 3.
2. Any employee may submit an additional AI tool to Legal for DPA and IP review. No additional tool is permitted until Legal issues written approval.
3. Sales employees may use AI-assisted drafting for external communications only through a tool approved under item 2 above. No AI-generated or AI-assisted text may be transmitted to customers, prospects, or partners without prior written approval from the sales manager, documented in email or messaging thread retained for audit.

---

## Prohibited Uses

1. **No customer data in third-party AI tools.** Inputting PII, financial data, or any customer-identifiable information into any AI service outside company-controlled systems is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms; SOC2 Type II, GDPR, and pending FedRAMP authorization require data handling controls.]*

2. **No AI-generated code merged without PR disclosure and license-identifier review.** Engineers must identify AI-generated code in the pull request description. Any PR containing a license identifier (e.g., GPL, MIT, Apache) in AI-generated code is held and referred to Legal before merge. Reviewing managers must reject any PR lacking this disclosure field. *[Basis: Incident 3—intern committed AI-generated code containing a GPL license header; outside counsel confirmed AI-generated code may not be copyrightable, creating ownership risk in merged code.]*

3. **No unapproved AI tools.** No employee may use any AI tool for work purposes other than GitHub Copilot Business under an assigned seat or a tool approved in writing by Legal. *[Basis: No tool other than GitHub Copilot Business has received Legal DPA and IP review; Incidents 1, 2, and 3 each resulted from use of unreviewed tools; outside counsel confirmed inputting customer data into third-party AI services likely violates existing DPA terms.]*

---

## Enforcement

1. Any employee, manager, or reviewer who discovers a violation must file a SOC2 incident report the same business day via existing SOC2 incident reporting channels.
2. Confirmed violations follow the existing disciplinary process: documented warning, performance plan, or termination.
3. Managers are accountable for violations by direct reports where required documentation was not collected or verified; absence of documentation is treated as a process failure subject to the disciplinary process in item 2.

---

CEO Signature: ___________________________ Date: ___________________________

---

**Synthesis rationale by dimension:**

- **Scope item 2:** Taken from Version Y. The affirmative statement that GitHub Copilot Business is the sole approved tool is operationally stronger than Version X's navigational redirect.

- **Permitted Uses item 1:** Merged both versions. Version Y's seat-assignment accountability sentence is retained; Version X's cleaner seat-permission framing is preserved.

- **Permitted Uses item 3 (sales drafting):** Retained from Version X, with one modification: the permission is conditioned on Legal approval under item 2, resolving Version Y's valid objection that no sales AI tool has been approved. This preserves the policy's coverage of a documented incident class (Incident 2) without granting permission for an unapproved tool, and uses existing email and messaging threads for audit—no new tooling required.

- **Prohibited Uses item 2 (PR disclosure):** Merged. Version Y's affirmative manager-rejection obligation is added to Version X's disclosure requirement, converting self-reporting into an enforced gate at an existing process step.

- **Prohibited Uses item 3 (unapproved tools):** Version Y's formulation is stronger because it is affirmative and covers all employees by role rather than by residual exclusion.

- **Prohibited Uses basis citations:** Version X's fuller narrative citations are retained where they add traceability; condensed where space requires.

- **Enforcement:** Both versions are substantively identical; Version Y's "collected or verified" language in item 3 is marginally more precise and is retained.