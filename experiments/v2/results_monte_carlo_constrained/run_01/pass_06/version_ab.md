# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee on company devices or for company work.
2. This policy covers company-licensed tools and personal or free-tier tools used for company purposes.
3. Compliance is required to maintain SOC2 Type II certification, meet GDPR obligations for EU customers, and satisfy pending FedRAMP authorization requirements.
4. Company survey data shows 73% of engineers and 45% of sales staff currently use AI tools; this policy establishes the rules governing that use.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI tool. Use is limited to the 80 licensed seats; Engineering leadership assigns and revokes seats upon request.
2. Copilot-seated engineers may use GitHub Copilot for code completion, boilerplate generation, and test writing.
3. All AI-generated code must pass human pull request review before merge. Reviewers are accountable for confirming the absence of third-party license headers and verbatim copied content before approving.
4. Additional AI tools require joint written sign-off from Engineering and Finance within the $50K annual budget.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms, creating GDPR liability; this also implicates pending FedRAMP authorization controls.]*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects without human review confirming it contains no third-party copyrighted material. *[Basis: Incident 2—sales rep sent AI output containing verbatim competitor copyrighted marketing copy.]*
3. **No commits containing AI-generated code with third-party license headers.** Reviewers must reject any pull request carrying such a header, including GPL. *[Basis: Incident 3—intern committed code with a GPL header sourced from AI training data, creating IP ownership risk.]*
4. **Slack AI features must remain disabled.** No employee may request or self-enable AI features within company Slack. *[Basis: Slack AI features are currently disabled; enabling them routes company and customer data through an unapproved external AI service, violating DPA terms per outside counsel.]*
5. **No representation of AI-generated work as independently copyrightable company IP** in contracts, filings, or customer deliverables. *[Basis: Outside counsel flagged that AI-generated code may not be copyrightable.]*

---

## Enforcement

1. Violations are reported to the employee's direct manager within one business day of discovery.
2. The manager opens a formal HR investigation within five business days of the report; confirmed violations result in disciplinary action up to and including termination.
3. Incidents involving customer data exposure are referred to Legal immediately upon discovery.
4. Prohibited Use #1: No existing tool captures external service use; manager attestation and HR incident records constitute the audit trail, and managers are responsible for intake and documentation.
5. Prohibited Use #2: Outbound email records and CRM activity logs constitute the audit trail; Sales management reviews flagged communications upon complaint or spot-check.
6. Prohibited Use #3: Pull request history constitutes the audit trail; Engineering leadership reviews logs quarterly.
7. Prohibited Use #4: Slack workspace admin logs record any request to enable AI features; the Slack administrator denies all such requests.
8. Prohibited Use #5 and Permitted Uses #4: Legal reviews all customer contracts and IP filings before execution; Finance records of joint sign-off constitute the audit trail for unapproved tool spend.