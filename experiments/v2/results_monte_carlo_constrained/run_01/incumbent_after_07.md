# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee on company devices or for company work.
2. This policy covers company-licensed tools and personal or free-tier tools used for company purposes.
3. Compliance with this policy is required to maintain SOC2 Type II certification, meet GDPR obligations for EU customers, and satisfy pending FedRAMP authorization requirements.

---

## Permitted Uses

1. **GitHub Copilot Business** is the default approved AI coding tool. Engineering leadership assigns and revokes the 80 licensed seats; no seat may be shared.
2. Copilot-seated engineers may use GitHub Copilot for code completion, boilerplate generation, and test writing within the licensed environment.
3. All AI-generated code must pass human pull request review before merge. Reviewers must reject any pull request containing identifiable third-party license headers.
4. Additional AI tools may be approved through joint written sign-off from the heads of Engineering, Legal, and Finance, within the $50K annual budget. Approved tools are added to this policy by amendment before use begins.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms and creates GDPR liability; it also implicates pending FedRAMP authorization controls.]*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects without human review confirming it contains no third-party copyrighted material. *[Basis: Incident 2—sales rep sent AI output containing verbatim competitor copyrighted marketing copy.]*
3. **No commits containing AI-generated code with third-party license headers.** Reviewers must reject any pull request carrying such a header, including GPL. *[Basis: Incident 3—intern committed code with a GPL header sourced from AI training data, creating IP ownership risk.]*
4. **Slack AI features must remain disabled.** No employee may request or self-enable AI features within company Slack. *[Basis: Slack AI features are currently disabled; enabling them routes company and customer data through an unapproved external AI service, violating DPA terms per outside counsel.]*
5. **No representation of AI-generated work as independently copyrightable company IP** in contracts, filings, or customer deliverables. *[Basis: Outside counsel flagged that AI-generated code may not be copyrightable; Incident 3 demonstrated that AI output can carry third-party IP encumbrances, compounding ownership uncertainty.]*

---

## Enforcement

1. **Graduated consequences:** First confirmed violation results in a written warning. Second violation results in suspension of AI tool access and a performance improvement plan. Third violation, or any single violation involving customer data exposure, results in termination.
2. Legal holds final authority on policy interpretation disputes.
3. Violations are reported to the employee's direct manager within one business day of discovery. The manager opens a formal HR investigation within five business days. Legal is notified immediately for any incident involving customer data.
4. **Prohibited Use #1 audit trail:** GitHub Copilot Business logs confirm use of the approved service. Reports of external AI service use are documented in HR incident records; managers are responsible for intake and documentation.
5. **Prohibited Use #2 audit trail:** Sales management reviews outbound email records and CRM activity logs monthly; flagged communications are escalated to Legal within two business days.
6. **Prohibited Use #3 audit trail:** Pull request history in the existing version control system constitutes the audit trail; Engineering leadership reviews logs quarterly.
7. **Prohibited Use #4 audit trail:** Slack workspace admin logs record all requests to enable AI features; the Slack administrator denies all such requests and logs each denial.
8. **Prohibited Use #5 audit trail:** Legal reviews all customer contracts and IP filings before execution and rejects any representation of AI output as independently copyrightable.
9. **Permitted Use #4 audit trail:** Finance records of joint written sign-off constitute the audit trail for any approved additional tool spend.