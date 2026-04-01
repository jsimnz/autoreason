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

---

**Synthesis rationale by dimension:**

- **Scope:** Version Y's tighter three-item structure is superior. The factual recital about current usage rates (Version X item 2) is not a scope statement and was correctly removed. The Slack item is retained as a factual statement only, without the ungrounded Legal-approval re-enabling requirement Version X added.
- **Permitted Uses:** Version Y is superior on both items. The sales email-drafting item (Version Y item 2) correctly addresses the 45% of sales staff already using AI tools—a gap Version X left entirely unaddressed. Version X's tool-request process item was redundant with Scope and correctly removed.
- **Prohibited Uses:** Version Y's PR certification mechanism (item 4) is superior to Version X's merge-approval-hold mechanism. The certification places the obligation on the submitting engineer using the existing PR submission process, satisfying the constraint that enforcement require no new tooling. Version X's mechanism imposed a new screening obligation on reviewers. All five prohibitions are otherwise equivalent; Version Y's slightly tighter phrasing on item 5 is adopted.
- **Enforcement:** Version Y's three-item structure is superior. Removing Version X's manager-accountability item (item 4) is correct: the PR certification requirement in Prohibited Use item 4 already places the obligation on the engineer, making the circular manager-screening enforcement redundant and potentially unenforceable.