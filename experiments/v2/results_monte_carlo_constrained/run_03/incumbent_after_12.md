I'll address each problem in turn, then present the revised document.

**Problem 1 (word count):** Cut prose throughout, especially in Prohibited Uses parentheticals and Enforcement items, to bring the body under 500 words.

**Problem 2 (prose paragraphs in Enforcement):** Split every multi-sentence Enforcement item into discrete, single-purpose numbered items.

**Problem 3 (FedRAMP causal inference):** Remove the "jeopardizes FedRAMP authorization" language from Prohibited Use 4. Replace with a direct citation to the base facts that do support the prohibition (DPA terms, SOC2).

**Problem 4 (company devices/accounts/networks scope qualifier):** Remove that qualifier from Prohibited Use 5. The prohibition applies without a device-scope limitation, consistent with the base facts.

**Problem 5 (mandatory revert protocol):** Remove the standing revert workflow from Enforcement. Retain only the PR block and escalation steps, which rely on existing review processes.

**Problem 6 (two-strike termination rule):** Remove the specific disciplinary escalation structure entirely. No base fact supports it.

**Problem 7 (cross-reference by number):** Rewrite Permitted Use 3 to be self-contained, removing the "Prohibited Use 5" reference.

**Problem 8 (data processor legal characterization):** Rewrite Scope item 3 to track the base facts exactly: the company handles customer PII and financial data and has GDPR obligations for EU customers.

---

**TO:** All Employees, Contractors, and Interns
**FROM:** Office of the CEO
**DATE:** [Date]
**SUBJECT:** AI Tool Usage Policy — Effective Immediately

---

# AI Tool Usage Policy

## Scope

1. Applies to all employees, contractors, and interns across all functions, effective immediately.
2. Covers any use of AI tools for work-related tasks including coding, writing, data analysis, and customer communications.
3. Covers all customer PII and financial data subject to the company's GDPR obligations for EU customers.

## Permitted Uses

1. **Approved tool:** GitHub Copilot Business only. Engineering leadership manages the 80 licensed seats.
2. **Authorized use:** Assigned seat holders may use GitHub Copilot for code suggestions, boilerplate generation, and test writing.
3. **Engineers without an assigned seat** may not use any AI coding tool until a seat is assigned or an alternative tool receives documented CTO and Legal approval.
4. **Tool expansion:** Requests for additional AI tools require written approval from CTO and Legal before use begins.

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or customer-identifiable information into any non-approved AI service is prohibited. *(Incident 1 — engineer pasted a customer database schema into ChatGPT; outside counsel finding that doing so violates existing DPA terms; SOC2 Type II certification; GDPR obligations for EU customers.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects unless the sender's manager confirms review for accuracy, originality, and legal compliance in the same thread before sending. *(Incident 2 — sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code committed without license review.** Code produced by AI tools may not be committed unless the pull request reviewer confirms in the PR record that no third-party license headers or GPL-encumbered content are present. *(Incident 3 — intern committed code containing a GPL license header; outside counsel finding that AI-generated code may not be copyrightable.)*
4. **Slack AI features must remain disabled.** Enabling or circumventing disabled AI features in company Slack is prohibited. *(Doing so routes data through third-party AI services, violating existing DPA terms and SOC2 controls.)*
5. **No unapproved AI tools.** Using non-approved AI services for work-related tasks without documented CTO and Legal approval is prohibited. *(GitHub Copilot Business is the only assessed tool; unapproved tools have not been reviewed for DPA, SOC2, or GDPR compliance.)*

## Enforcement

1. Violations involving customer data (Prohibited Uses 1, 4) are escalated immediately to Security and Legal for breach assessment.
2. PR reviewers who identify AI-generated code lacking required license confirmation block the merge and notify engineering leadership.
3. Engineering leadership logs the incident before any merge proceeds.
4. Managers whose direct reports trigger Prohibited Use 2 notify Legal and document the incident in the employee's HR file.
5. Managers who identify use of unapproved AI tools or Slack AI circumvention revoke access to the service and notify Security and Legal.
6. All violations are documented in the employee's HR file and subject to disciplinary action up to and including termination.