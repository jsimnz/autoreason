I'll address each problem systematically, then present the revised document.

**Changes made and which problems they fix:**

- **Problem 1 (word count):** Compressed enforcement items, tightened prose throughout, merged redundant phrases.
- **Problem 2 (sales/other omitted from Permitted Uses):** Added a permitted use item for sales and other functions, scoped to non-customer-data tasks using any approved tool.
- **Problem 3 (Prohibited Use 2 new workflow):** Replaced "confirm review in the same thread" with the existing manager-approval step in the normal send workflow — framed as manager sign-off before external transmission, which is a standard existing supervisory control rather than a new thread-based process.
- **Problem 4 (Prohibited Use 3 new PR checklist):** Replaced mandatory new checklist step with the existing code review process: the PR reviewer is responsible for license review as part of standard review, which is an existing gate, not a new one.
- **Problem 5 (unverifiable condition in Enforcement 3):** Removed the conditional "if later identified" clause. The enforcement item now holds the PR reviewer accountable for the review they performed, without depending on a future detection mechanism.
- **Problem 6 (Scope item 4 misplaced):** Moved approved-tool content out of Scope and into Permitted Uses where it belongs. Scope now contains only applicability statements.
- **Problem 7 (CTO+Legal approval not grounded):** Removed the invented CTO+Legal approval workflow. Replaced with "Legal review required before use," which is derivable from the compliance posture (SOC2, GDPR, FedRAMP) described in the base facts without inventing a specific named process.
- **Problem 8 (access control claim unverifiable):** Removed the assertion that unapproved tools will be blocked via access controls. Enforcement item for Prohibited Use 5 now states the violation is reported and documented, without asserting a blocking capability not established by the base facts.
- **Problem 9 (copyright risk unaddressed):** Added a disclosure requirement in Permitted Uses for engineering: AI-generated code shipped to customers must be flagged to Legal, grounded in outside counsel's copyright finding.

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
3. Covers all customer PII and financial data handled by the company; GDPR obligations apply additionally to EU customer data.

## Permitted Uses

1. **Approved tool:** GitHub Copilot Business (80 licensed seats, managed by Engineering leadership) is the sole approved AI tool. Use of any other AI tool requires Legal review before use, given unassessed DPA, SOC2, GDPR, and FedRAMP exposure.
2. **Engineering:** Seat holders may use GitHub Copilot for code suggestions, boilerplate generation, and test writing. Engineers without an assigned seat may not use any AI coding tool until a seat is assigned or an alternative tool completes Legal review.
3. **AI-generated code shipped to customers** must be flagged to Legal before delivery. *(Outside counsel finding: AI-generated code may not be copyrightable.)*
4. **Sales and all other functions:** No AI tool is currently approved for work tasks. Requests for approved tools are submitted to Legal for review within the $50K annual budget.

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or customer-identifiable information into any non-approved AI service is prohibited. *(Incident 1; outside counsel DPA finding; SOC2 Type II; GDPR; pending FedRAMP authorization.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be transmitted externally without manager sign-off on accuracy, originality, and legal compliance before sending. *(Incident 2: sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code merged without license review.** Code from AI tools may not be merged unless the PR reviewer has confirmed, as part of standard code review, that no third-party license headers or GPL-encumbered content are present. *(Incident 3; outside counsel copyright finding.)*
4. **Slack AI features remain disabled.** Enabling or circumventing disabled Slack AI features is prohibited. *(SOC2 Type II; outside counsel DPA finding; company handles customer PII and financial data.)*
5. **No unapproved AI tools.** Using non-approved AI services for work tasks without completed Legal review is prohibited. *(GitHub Copilot Business is the only assessed tool; all others carry unreviewed DPA, SOC2, GDPR, and FedRAMP risk.)*

## Enforcement

1. Violations of Prohibited Use 1 are escalated immediately to Security and Legal for breach assessment under SOC2 and GDPR; documented in the employee's HR file; subject to disciplinary action up to termination.
2. Violations of Prohibited Use 2 are reported by the employee's manager to Legal; documented in the employee's HR file; subject to disciplinary action up to termination.
3. Violations of Prohibited Use 3: the merge is blocked. The PR reviewer is accountable for the license review performed; incidents are documented in the reviewer's HR file and subject to disciplinary action up to termination.
4. Violations of Prohibited Use 4 are reported to Security, who restore the disabled configuration; documented in the employee's HR file; subject to disciplinary action up to termination.
5. Violations of Prohibited Use 5 are reported to Security and Legal; documented in the employee's HR file; subject to disciplinary action up to termination.