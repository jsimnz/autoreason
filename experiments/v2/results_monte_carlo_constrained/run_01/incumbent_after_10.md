# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee on company devices or for company work.
2. This policy covers both company-licensed tools and personal or free-tier tools used for company purposes.
3. Compliance is required to maintain SOC2 Type II certification, meet GDPR obligations for EU customers, and satisfy pending FedRAMP authorization requirements.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding tool. Engineering leadership assigns and revokes the 80 licensed seats; no seat may be shared.
2. Copilot-seated engineers may use GitHub Copilot for code completion, boilerplate generation, and test writing within the licensed environment only.
3. All AI-generated code must pass human pull request review before merge.
4. Additional AI tools may be approved through joint written sign-off from the heads of Engineering and Legal, within the $50K annual budget. Approved tools are added to this policy by amendment before use begins.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—an engineer pasted a customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms and creates GDPR and FedRAMP liability.]*
2. **No unreviewed AI-generated content used externally.** Any employee must confirm, before use, that AI-generated text contains no third-party copyrighted material. *[Basis: Incident 2—a sales rep used AI-generated text that included a competitor's copyrighted marketing copy verbatim.]*
3. **No commits containing AI-generated code with third-party license headers.** Pull request reviewers must reject any pull request carrying such a header; pull request history constitutes the audit trail. *[Basis: Incident 3—an intern committed AI-generated code carrying a GPL license header sourced from AI training data.]*
4. **Slack AI features must remain disabled.** No employee may request or self-enable AI features within company Slack; the Slack administrator logs and denies all such requests. *[Basis: Outside counsel confirmed that enabling Slack AI features routes company and customer data through an unapproved external AI service, violating existing DPA terms.]*
5. **No representation of AI-generated code as independently copyrightable company IP** in contracts or customer deliverables. The responsible employee's manager reviews any flagged contract language before execution. *[Basis: Outside counsel flagged that AI-generated code may not be copyrightable; Incident 3 demonstrated that AI output can carry third-party IP encumbrances.]*

---

## Enforcement

1. Violations are reported to the employee's direct manager upon discovery.
2. Legal is notified immediately for any incident involving customer data.
3. A confirmed violation results in revocation of AI tool access pending manager review.
4. Managers document all confirmed violations in HR incident records, which constitute the official violation log.