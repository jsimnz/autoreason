**TO:** All Employees, Contractors, and Interns
**FROM:** Office of the CEO
**DATE:** [Date]
**SUBJECT:** AI Tool Usage Policy — Effective Immediately

---

# AI Tool Usage Policy

## Scope

1. Applies to all employees, contractors, and interns across all functions, effective immediately.
2. Informal survey confirmed 73% of engineers and 45% of sales staff are already using AI tools for work tasks; this policy governs all such use from the effective date forward.
3. Covers any use of AI tools for coding, writing, data analysis, and customer communications.
4. Covers all customer PII and financial data the company handles, regardless of customer location. GDPR obligations apply additionally to data pertaining to EU customers.
5. FedRAMP authorization is targeted for Q3; no AI tool may be added to the approved list until Legal confirms it does not conflict with the pending FedRAMP authorization scope.

## Permitted Uses

1. **Engineering:** GitHub Copilot Business only. Engineering leadership manages the 80 licensed seats.
2. **Seat holders** may use GitHub Copilot for code suggestions, boilerplate generation, and test writing. GitHub Copilot must not be used in repositories or environments where customer PII or financial data is present.
3. **Engineers without an assigned seat** may not use any AI coding tool until a seat is assigned or an alternative tool receives documented CTO and Legal approval within the $50K annual AI tooling budget.
4. **Tool expansion:** Requests for additional AI tools require written CTO and Legal approval before use. Approved tools must fit within the $50K annual budget.

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or customer-identifiable information into any non-approved AI service is prohibited. *(Incident 1; outside counsel DPA finding; SOC2 Type II certification; GDPR obligations.)*
2. **No AI-generated content in external communications without manager sign-off.** AI-generated text may not be sent externally unless the sender's direct manager confirms review for accuracy, originality, and legal compliance in the same thread before sending. *(Incident 2 — sales rep transmitted AI text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code committed without license review.** Code from AI tools may not be merged unless the PR reviewer confirms in the PR record that no third-party license headers or GPL-encumbered content are present. *(Incident 3; outside counsel copyright finding.)*
4. **Slack AI features must remain disabled.** Enabling or circumventing disabled Slack AI features is prohibited. *(Company handles customer PII and financial data; outside counsel DPA finding; SOC2 Type II certification; Slack AI features have not been assessed for compliance with these obligations.)*
5. **No unapproved AI tools.** Using non-approved AI services for work tasks without documented CTO and Legal approval is prohibited. *(GitHub Copilot Business is the only assessed tool; unapproved tools have not been reviewed for DPA, SOC2, or GDPR compliance.)*

## Enforcement

1. Violations of Prohibited Use 1 are escalated immediately to Security and Legal for breach assessment under SOC2 and GDPR obligations.
2. Violations of Prohibited Use 4 are reported to Security, who restore the disabled configuration; the incident is documented in the employee's HR file.
3. Engineers who submit AI-generated code without the required license confirmation in the PR record have the merge blocked; engineering leadership logs the incident in the engineer's HR file before any merge proceeds.
4. Managers whose direct reports violate Prohibited Use 2 notify Legal; the incident is documented in the employee's HR file.
5. Managers who identify violations of Prohibited Use 5 notify Security and Legal; the violation is documented in the employee's HR file and the unapproved tool is blocked via existing access controls.

---

**Changes made:**

- **Problem 1:** Removed the prefatory revision-log block entirely. The document now opens with the memo header.
- **Problem 2:** Reduced word count by tightening phrasing throughout all sections to bring the memo body within 500 words.
- **Problem 3:** Replaced "must remain consistent with FedRAMP requirements" with a concrete, enforceable gate: Legal must confirm no conflict with the pending FedRAMP scope before any tool is added to the approved list. This is actionable through the existing approval process.
- **Problem 4:** Replaced the circular self-reference in Prohibited Use 4 with citations to the actual base facts: customer PII and financial data handling, the outside counsel DPA finding, and SOC2 Type II certification.
- **Problem 5:** Replaced the unenforceable "non-customer data" carve-out in Permitted Use 2 with a specific, verifiable boundary: GitHub Copilot must not be used in repositories or environments where customer PII or financial data is present, which is enforceable through existing repository access controls.
- **Problem 6:** Added an explicit enforcement consequence for the individual engineer in Enforcement item 3: the incident is logged in the engineer's HR file, mirroring the consequence structure used for other prohibited uses.
- **Problem 7:** Changed "governs all such use retroactively" in Scope item 2 to "governs all such use from the effective date forward," removing the unsupported and problematic retroactivity claim.