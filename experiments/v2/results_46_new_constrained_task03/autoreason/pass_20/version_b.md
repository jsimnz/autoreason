I'll address each problem in turn, then present the revised document.

**Changes made and their motivation:**

- **Problem 1 (word count):** Cut Scope item 2 (also fixes Problem 7), cut Permitted Uses item 2 (also fixes Problem 8), compressed Scope item 4 (also fixes Problem 6), and tightened prose throughout to bring body text under 500 words.
- **Problem 2 & 3 (sales use cases missing):** Added a Permitted Uses item explicitly addressing sales staff email drafting with the constraint that no customer data is included, making the prohibition-by-default explicit and intentional.
- **Problem 4 (merge-approval not an existing control):** Replaced the "held at merge-approval step" mechanism with a requirement that the engineer submitting the PR certify in the PR description that AI-generated code contains no license identifiers — this uses the existing PR submission process rather than imposing a new screening obligation on reviewers.
- **Problem 5 (circular manager accountability):** Removed Enforcement item 4. The PR certification requirement in Prohibited Use item 4 places the obligation on the submitting engineer, eliminating the need for manager-level screening enforcement.
- **Problem 6 (Slack re-enabling requirement not derivable):** Removed the Legal-approval requirement for re-enabling Slack AI; the item now states only that Slack AI features are currently disabled.
- **Problem 7 (Scope item 2 is a factual recital, not a scope statement):** Removed Scope item 2 entirely.
- **Problem 8 (Permitted Uses item 2 is filler):** Removed the tool-request process item from Permitted Uses. The tool-approval process is already captured in Scope item 3.

---

# AI Tool Usage Policy
**Effective Date:** Date of CEO signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI tools used for any work purpose by all employees, on any device.
2. The only approved AI tools at issuance are: GitHub Copilot Business (80 licensed seats, managed by Engineering leadership) and any tool for which Legal has issued prior written approval following DPA and IP review. All other tools are unapproved.
3. Company Slack AI features are currently disabled.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, generation, and review in approved repositories. Engineers without an assigned seat may not use Copilot.
2. Sales staff may use approved AI tools to draft external emails, provided no customer PII or financial data is included in any prompt or input.

---

## Prohibited Uses

1. **No customer data in unapproved AI tools.** Inputting PII, financial data, or any customer-identifiable information into any unapproved AI service is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel DPA violation finding; SOC2 Type II, GDPR, and pending FedRAMP obligations.]*
2. **No distribution of AI-generated content reproducing copyrighted material verbatim.** Employees must not send, publish, or commit AI-generated content that reproduces third-party copyrighted material verbatim. *[Basis: Incident 2—sales rep distributed AI-generated text reproducing a competitor's copyrighted marketing copy verbatim; IP risk flagged by outside counsel.]*
3. **No unapproved AI tools.** Employees must not use any AI tool for work purposes other than tools approved under Scope item 2. *[Basis: Incidents 1, 2, and 3 each involved unapproved tools; outside counsel IP and copyright findings arose directly from that use.]*
4. **No submitting AI-generated code containing license identifiers without Legal clearance.** Engineers must certify in the PR description that AI-generated code contains no license identifiers. Any PR where that certification cannot be made must be referred to Legal before submission. *[Basis: Incident 3—intern committed AI-generated code containing a GPL license header; copyright risk flagged by outside counsel.]*
5. **No asserting company copyright over AI-generated code without Legal clearance.** Employees must not claim company ownership over AI-generated code without prior written clearance from Legal. *[Basis: Outside counsel finding that AI-generated code may not be copyrightable.]*

---

## Enforcement

1. Violations involving customer PII or financial data require a SOC2 incident report and notification to Legal for GDPR and FedRAMP assessment.
2. All other violations must be reported via existing SOC2 incident reporting channels.
3. Violations follow the existing disciplinary process: documented warning, performance plan, or termination.

---

CEO Signature: ___________________________ Date: ___________________________