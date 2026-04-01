# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI-powered tools—including code assistants, writing assistants, and generative models—by all 200 employees across engineering, sales, and all other functions.
2. This policy applies to both company-licensed tools and personal or free-tier AI tools accessed on company devices or for company work.
3. Compliance with this policy is required to maintain SOC2 Type II certification, GDPR obligations, and FedRAMP authorization targeted for Q3.

---

## Permitted Uses

1. **GitHub Copilot Business** is the approved AI coding assistant. Use is limited to the 80 licensed seats; Engineering leadership assigns and revokes seats.
2. Engineers may use GitHub Copilot Business for code completion, boilerplate generation, and test writing on internal or proprietary codebases containing no customer PII or financial data.
3. Sales employees may use AI drafting tools solely for internal template creation and non-customer-specific content. All outbound customer communications require human review before sending.
4. All AI-generated code must be reviewed in pull requests by a human engineer before merge. Reviewers are responsible for confirming the absence of third-party license headers or identifiable copied content.
5. The $50K annual AI tooling budget is administered by Engineering and Finance jointly; no new AI tool may be expensed or deployed without written approval from both.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service (including free ChatGPT, Claude, or similar) is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms and creates GDPR liability.]*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects without a human review confirming it contains no third-party copyrighted material. *[Basis: Incident 2—sales rep sent AI output containing verbatim competitor copyrighted marketing copy.]*
3. **No AI-generated code may be committed without license header review.** Commits containing AI-generated code that carry any open-source license header (including GPL) are blocked from merge. *[Basis: Incident 3—intern committed code with a GPL header sourced from AI training data, creating IP ownership risk.]*
4. **Slack AI features remain disabled.** No employee may request or self-enable AI features within company Slack. *[Basis: Slack AI features are currently disabled; enabling them would create unreviewed data-sharing with a third-party AI service.]*
5. Employees may not represent AI-generated work product as independently copyrightable company IP in contracts, filings, or customer deliverables. *[Basis: Outside counsel flagged that AI-generated code may not be copyrightable.]*

---

## Enforcement

1. Violations are investigated by the employee's direct manager and HR within 5 business days of identification.
2. Confirmed violations result in: first offense—written warning and mandatory policy re-acknowledgment; second offense—revocation of AI tool access and performance review; third offense or any incident causing customer data exposure—termination and potential legal referral.
3. Pull request reviews and access logs for GitHub Copilot Business serve as the audit trail; no new tooling is required.
4. This policy is acknowledged via the existing annual policy sign-off process in the HR system.