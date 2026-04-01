I'll address each problem in turn, then present the revised document.

**Changes made and which problem each fixes:**

- **Problem 1 (word count):** Converted all prose items to short, atomic numbered items and cut all explanatory connective text. Removed Scope item 2 (also fixes Problem 3). Shortened basis citations throughout.
- **Problem 2 (numbered items vs. prose paragraphs):** Restructured every section so each numbered item is a single discrete rule, not a paragraph.
- **Problem 3 (Scope item 2 is filler):** Deleted it entirely.
- **Problem 4 ("materially rewritten" unenforceable):** Replaced with "must not be sent or published without the employee adding original substantive content." This is observable by a manager reviewing outbound communications—no new tooling required.
- **Problem 5 (invented 15-day timeline):** Removed the timeline entirely. Legal review completes before approval is issued; no duration specified.
- **Problem 6 (Slack AI features unaddressed):** Added a Scope item stating Slack AI features remain disabled and re-enabling them requires Legal written approval.
- **Problem 7 (enforcement not differentiated by severity):** Added a specific enforcement item requiring same-day regulatory incident reporting for violations involving customer data, separate from the general disciplinary path.
- **Problem 8 ("confirmed" overstates certainty):** Changed all instances to "flagged by outside counsel."

---

# AI Tool Usage Policy
**Effective Date:** Date of CEO signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI tools used for work purposes by all employees, on company or personal devices.
2. The sole approved AI tool is GitHub Copilot Business (80 licensed seats).
3. Company Slack AI features remain disabled. Re-enabling them requires prior written approval from Legal.
4. Any tool not listed in item 2 or approved in writing by Legal under Permitted Uses item 2 is unapproved.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, generation, and review in approved repositories. Seat assignment is managed by Engineering leadership.
2. Any employee may submit a written request to Legal to evaluate an additional AI tool. No additional tool is permitted until Legal issues written approval following DPA and IP review.

---

## Prohibited Uses

1. **No customer data in unapproved AI tools.** Inputting PII, financial data, or any customer-identifiable information into any unapproved AI service is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; DPA violation risk flagged by outside counsel; SOC2 Type II, GDPR, and pending FedRAMP obligations.]*
2. **No unreviewed AI-generated external content.** AI-generated content must not be sent or published without the employee adding original substantive content. Managers must verify this before approving outbound communications. *[Basis: Incident 2—sales rep sent AI-generated text reproducing competitor's copyrighted copy verbatim; IP risk flagged by outside counsel.]*
3. **No unapproved AI tools.** No employee may use any AI tool for work purposes other than tools approved under Permitted Uses. *[Basis: Incidents 1, 2, and 3 each involved unapproved tools; DPA violation risk flagged by outside counsel.]*
4. **No AI-generated code merged without PR disclosure and license review.** Engineers must identify AI-generated code in the pull request description. Any PR containing a license identifier in AI-generated code is held and referred to Legal before merge. Reviewing managers must reject any PR lacking this disclosure. *[Basis: Incident 3—intern committed AI-generated code containing a GPL license header; copyright risk flagged by outside counsel.]*

---

## Enforcement

1. Any violation involving customer PII or financial data requires a same-day SOC2 incident report via existing SOC2 channels and immediate notification to Legal for GDPR and FedRAMP regulatory assessment.
2. All other violations must be reported via existing SOC2 incident reporting channels by the end of the business day the violation is discovered.
3. Confirmed violations follow the existing disciplinary process: documented warning, performance plan, or termination.
4. Managers are accountable for violations by direct reports where required documentation was not collected or verified; absence of documentation is itself a violation subject to item 3.

---

CEO Signature: ___________________________ Date: ___________________________