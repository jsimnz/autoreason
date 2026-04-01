I'll address each problem in turn, then present the revised document.

**Changes made and problems addressed:**

- **Problem 1 (word count):** Tightened language throughout all sections; removed redundant phrasing and explanatory asides to bring the body under 500 words.
- **Problem 2 (Scope items as prose narrative):** Rewrote Scope items 2 and 5 as direct policy statements rather than contextual explanation.
- **Problem 3 (no enforcement for Prohibited Use 3):** Added a dedicated enforcement item for Prohibited Use 3 that states the consequence for a reviewer who falsely confirms license clearance.
- **Problem 4 (survey figure in Scope):** Removed the survey citation from Scope entirely; it carries no enforceable content.
- **Problem 5 (invented FedRAMP approval process):** Removed Scope item 5; the FedRAMP fact is already referenced where relevant in Prohibited Uses.
- **Problem 6 (customer data restriction on Copilot):** Removed the restriction on using GitHub Copilot near customer data environments; it is not derivable from the base facts.
- **Problem 7 (manager bears accountability, not employee):** Rewrote Enforcement item 4 to place the consequence on the violating employee directly; manager notification is retained as a procedural step, not the sole action.
- **Problem 8 (no HR consequence for Prohibited Use 5):** Added explicit disciplinary language to the Prohibited Use 5 enforcement item, matching the structure of other enforcement items.

---

**TO:** All Employees, Contractors, and Interns
**FROM:** Office of the CEO
**DATE:** [Date]
**SUBJECT:** AI Tool Usage Policy — Effective Immediately

---

# AI Tool Usage Policy

## Scope

1. Applies to all employees, contractors, and interns across all functions, effective immediately.
2. Governs all use of AI tools for coding, writing, data analysis, and customer communications.
3. Covers all customer PII and financial data the company handles. GDPR obligations apply additionally to data pertaining to EU customers.
4. GitHub Copilot Business (80 seats) is the sole approved AI tool. All other tools require documented CTO and Legal approval within the $50K annual budget before use.

## Permitted Uses

1. **Engineering:** GitHub Copilot Business only. Engineering leadership manages the 80 licensed seats.
2. **Seat holders** may use GitHub Copilot for code suggestions, boilerplate generation, and test writing.
3. **Engineers without an assigned seat** may not use any AI coding tool until a seat is assigned or an alternative tool receives documented CTO and Legal approval within the $50K annual budget.

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or customer-identifiable information into any non-approved AI service is prohibited. *(Incident 1; outside counsel DPA finding; SOC2 Type II certification; GDPR obligations; FedRAMP authorization pending Q3.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent externally unless the sender's direct manager confirms review for accuracy, originality, and legal compliance in the same thread before sending. *(Incident 2 — sales rep transmitted AI text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code merged without license review.** Code from AI tools may not be merged unless the PR reviewer confirms in the PR record that no third-party license headers or GPL-encumbered content are present. *(Incident 3; outside counsel copyright finding.)*
4. **Slack AI features remain disabled.** Enabling or circumventing disabled Slack AI features is prohibited. *(SOC2 Type II certification; outside counsel DPA finding; company handles customer PII and financial data.)*
5. **No unapproved AI tools.** Using non-approved AI services for work tasks without documented CTO and Legal approval is prohibited. *(GitHub Copilot Business is the only assessed tool; unapproved tools have not been reviewed for DPA, SOC2, GDPR, or FedRAMP compliance.)*

## Enforcement

1. Violations of Prohibited Use 1 are escalated immediately to Security and Legal for breach assessment under SOC2 and GDPR obligations; the violation is documented in the employee's HR file and is subject to disciplinary action up to termination.
2. Violations of Prohibited Use 2 are reported by the employee's manager to Legal; the violation is documented in the violating employee's HR file and is subject to disciplinary action up to termination.
3. Violations of Prohibited Use 3 result in the merge being blocked. If a PR reviewer provides false license confirmation and GPL-encumbered code is later identified, the incident is documented in that reviewer's HR file and is subject to disciplinary action up to termination.
4. Violations of Prohibited Use 4 are reported to Security, who restore the disabled configuration; the violation is documented in the employee's HR file and is subject to disciplinary action up to termination.
5. Violations of Prohibited Use 5 are reported to Security and Legal; the unapproved tool is blocked via existing access controls, the violation is documented in the employee's HR file, and the employee is subject to disciplinary action up to termination.