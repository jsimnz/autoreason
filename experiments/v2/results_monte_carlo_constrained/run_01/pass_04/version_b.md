I'll address each problem in order, then present the revised document.

**Changes made:**

- **Problem 1 (word count):** Cut aggressively throughout—condensed basis citations, tightened Enforcement items, removed redundant phrasing.
- **Problem 2 (Prohibited Use #4 circular basis):** Replaced the self-referential basis with the actual motivating facts: DPA terms and FedRAMP data-handling requirements.
- **Problem 3 (Scope item 4 is a directive):** Rewrote item 4 as a scope statement describing the population of prior informal use, removing the enforcement instruction.
- **Problem 4 (unenforceable carve-out):** Replaced the open-ended "compliant configuration" condition with a concrete, defined restriction: Copilot may not be used in repositories tagged as containing PII or financial data in GitHub, which is enforceable via existing repo access controls.
- **Problem 5 (internal contradiction):** Replaced "sole approved AI tool" with "currently approved AI tool," which is consistent with item 4 allowing future approvals.
- **Problem 6 (no guidance for sales/other staff):** Added explicit Copilot permissions for sales and other staff (writing assistance, excluding customer data), parallel to the engineering item.
- **Problem 7 (FedRAMP never cited as motivating basis):** Added FedRAMP as a co-basis on Prohibited Use #1, where data-handling violations most directly threaten the Q3 authorization.
- **Problem 8 (Enforcement item 4 is filler):** Removed it entirely.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee on company devices or for company work.
2. This policy covers both company-licensed tools and personal or free-tier tools used for company purposes.
3. Compliance is required to maintain SOC2 Type II certification, meet GDPR obligations for EU customers, and achieve FedRAMP authorization by Q3.
4. This policy applies to all current informal AI tool use, including the 73% of engineers and 45% of sales staff identified in the company survey as using unlicensed tools.

---

## Permitted Uses

1. **GitHub Copilot Business** is the currently approved AI tool. Use is limited to the 80 licensed seats; Engineering leadership assigns and revokes seats.
2. Copilot-seated engineers may use GitHub Copilot for code completion, boilerplate generation, and test writing in any repository not tagged as containing PII or financial data in GitHub. Repositories with those tags are off-limits to Copilot use.
3. Copilot-seated sales and non-engineering staff may use GitHub Copilot for writing assistance on internal drafts not containing customer PII or financial data.
4. All AI-generated code must pass human pull request review before merge. Reviewers are accountable for confirming the absence of third-party license headers and copied content.
5. Additional AI tools may be approved only with joint written sign-off from Engineering and Finance, within the $50K annual budget.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms, creating GDPR liability; this also threatens FedRAMP authorization by demonstrating inadequate data-handling controls.]*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects without human review confirming it contains no third-party copyrighted material. *[Basis: Incident 2—sales rep sent AI output containing verbatim competitor copyrighted marketing copy.]*
3. **No commits containing AI-generated code with open-source license headers.** Reviewers must reject any pull request carrying such a header, including GPL. *[Basis: Incident 3—intern committed code with a GPL header sourced from AI training data, creating IP ownership risk.]*
4. **Slack AI features must not be enabled.** No employee may request or self-enable AI features within company Slack. *[Basis: Outside counsel flagged that inputting company data into unauthorized third-party AI services violates DPA terms; enabling Slack AI would route company and potentially customer data through an unapproved external AI service.]*
5. **No representation of AI-generated work as independently copyrightable company IP** in contracts, filings, or customer deliverables. *[Basis: Outside counsel flagged that AI-generated code may not be copyrightable.]*

---

## Enforcement

1. Violations are investigated by the employee's direct manager and HR. Confirmed violations result in disciplinary action up to and including termination; incidents involving customer data exposure are referred to Legal.
2. For engineering: pull request history and GitHub Copilot Business access logs serve as the audit trail; no new tooling is required.
3. For sales: outbound email records and CRM activity logs serve as the audit trail for compliance with Prohibited Use #2; no new tooling is required.