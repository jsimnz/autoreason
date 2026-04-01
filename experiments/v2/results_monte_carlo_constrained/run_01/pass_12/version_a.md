# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee on company devices or for company work.
2. This policy covers both company-licensed tools and personal or free-tier tools used for company purposes.
3. Compliance with this policy is required to maintain SOC2 Type II certification and meet GDPR obligations for EU customers; it also applies to all work subject to the pending FedRAMP authorization.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding tool. Engineering leadership assigns and revokes the 80 licensed seats; no seat may be shared.
2. Copilot-seated engineers may use GitHub Copilot for code completion, boilerplate generation, and test writing within the licensed environment only.
3. All AI-generated code must pass human pull request review before merge.
4. Additional AI tools require joint written sign-off from the heads of Engineering and Legal before any use begins, within the $50K annual budget. Written approval is added to this policy by amendment; use before amendment is complete is a policy violation.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—an engineer pasted a customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms and creates GDPR and FedRAMP liability.]*
2. **No AI-generated external content without manager review.** AI-generated text intended for external use must be reviewed and approved by the employee's direct manager before distribution. *[Basis: Incident 2—a sales rep used AI-generated text that included a competitor's copyrighted marketing copy verbatim. Manager approval is an existing process requiring no new tooling.]*
3. **No commits containing AI-generated code with third-party license headers.** Pull request reviewers must reject any pull request carrying such a header; pull request history constitutes the audit trail. *[Basis: Incident 3—an intern committed AI-generated code carrying a GPL license header from AI training data.]*
4. **Slack AI features must remain disabled.** No employee may request or self-enable AI features within company Slack; the Slack administrator logs and denies all such requests. *[Basis: Company Slack has AI features disabled; outside counsel confirmed that inputting customer data into third-party AI services violates existing DPA terms.]*
5. **No representation of AI-generated code as independently copyrightable company IP** in contracts or customer deliverables. The responsible employee's manager reviews any flagged contract language before execution. *[Basis: Outside counsel flagged that AI-generated code may not be copyrightable; Incident 3 demonstrated that AI output can carry third-party license headers.]*

---

## Enforcement

1. Violations are reported to the employee's direct manager upon discovery.
2. Legal is notified immediately for any incident involving customer data.
3. A confirmed violation results in revocation of AI tool access, enforced by Engineering leadership using existing GitHub Copilot seat controls and Slack administrator controls.
4. For employees without AI tool access to revoke—including sales staff using personal or free-tier tools—a confirmed violation results in written notice placed in the employee's existing HR file, with a mandatory manager review within five business days.
5. Managers document all confirmed violations in the employee's existing HR file, which constitutes the official violation log.