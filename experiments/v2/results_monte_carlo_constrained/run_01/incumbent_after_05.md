# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee on company devices or for company work.
2. This policy covers both company-licensed tools and personal or free-tier tools used for company purposes.
3. Compliance is required to maintain SOC2 Type II certification and meet GDPR obligations for EU customers; FedRAMP authorization obligations apply independently.
4. This policy applies to all current informal AI tool use, including the 73% of engineers and 45% of sales staff identified in the company survey as using AI tools without a company-approved tool.

---

## Permitted Uses

1. **GitHub Copilot Business** is the currently approved AI tool. Use is limited to the 80 licensed seats; Engineering leadership assigns and revokes seats upon request.
2. Copilot-seated engineers may use GitHub Copilot for code completion, boilerplate generation, and test writing only in repositories where a GitHub organization admin has enabled Copilot access; use in all other repositories is prohibited.
3. All AI-generated code must pass human pull request review before merge. Reviewers are accountable for confirming the absence of third-party license headers and identifiable copied content before approving.
4. Additional AI tools may be approved only with joint written sign-off from Engineering and Finance, within the $50K annual budget.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms, creating GDPR liability.]*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects without human review confirming it contains no third-party copyrighted material. *[Basis: Incident 2—sales rep sent AI output containing verbatim competitor copyrighted marketing copy.]*
3. **No commits containing AI-generated code with open-source license headers.** Reviewers must reject any pull request carrying such a header, including GPL. *[Basis: Incident 3—intern committed code with a GPL header sourced from AI training data, creating IP ownership risk.]*
4. **Slack AI features must remain disabled.** No employee may request or self-enable AI features within company Slack. *[Basis: Slack AI features are currently disabled; enabling them would route company and customer data through an unapproved external AI service, violating DPA terms per outside counsel.]*
5. **No representation of AI-generated work as independently copyrightable company IP** in contracts, filings, or customer deliverables. *[Basis: Outside counsel flagged that AI-generated code may not be copyrightable.]*

---

## Enforcement

1. Violations are reported to the employee's direct manager, who opens a formal HR investigation within five business days; confirmed violations result in disciplinary action up to and including termination; incidents involving customer data exposure are referred to Legal immediately.
2. Prohibited Uses #1 and #3: GitHub Copilot Business access logs and pull request history constitute the audit trail; Engineering leadership reviews logs quarterly.
3. Prohibited Use #2: Outbound email records and CRM activity logs constitute the audit trail; Sales management reviews flagged communications upon complaint or spot-check.
4. Prohibited Use #4: Slack workspace admin logs record any request to enable AI features and constitute the audit trail; the Slack administrator denies all such requests.
5. Prohibited Use #5: Legal reviews all customer contracts and IP filings before execution; employees must disclose AI tool use in the pull request or document submission where AI tools were used.