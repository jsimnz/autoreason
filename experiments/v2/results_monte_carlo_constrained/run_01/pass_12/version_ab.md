# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee on company devices or for company work, including personal or free-tier tools used for company purposes.
2. An internal survey found 73% of engineers and 45% of sales staff already use AI tools without an official policy; this policy governs all such existing and future use.
3. Compliance with this policy is required to maintain SOC2 Type II certification, meet GDPR obligations for EU customers, and satisfy requirements under the pending FedRAMP authorization.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding tool. Engineering leadership assigns and revokes the 80 licensed seats; no seat may be shared.
2. Copilot-seated engineers may use GitHub Copilot for code completion, boilerplate generation, and test writing within the licensed environment only.
3. All AI-generated code must receive human reviewer approval before merge.
4. Additional AI tools require joint written sign-off from the heads of Engineering and Legal before any use begins. Use without that sign-off is a policy violation.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—an engineer pasted a customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms and creates GDPR and FedRAMP liability.]*
2. **No AI-generated external content without manager approval.** AI-generated text intended for external distribution must be reviewed and approved by the employee's direct manager before sending. *[Basis: Incident 2—a sales rep distributed AI-generated text containing a competitor's copyrighted marketing copy verbatim. Manager approval is an existing process requiring no new tooling.]*
3. **No commits containing AI-generated code with third-party license headers.** Pull request reviewers must reject any pull request carrying such a header; pull request history constitutes the audit trail. *[Basis: Incident 3—an intern committed AI-generated code carrying a GPL license header originating from AI training data.]*
4. **Slack AI features must remain disabled.** No employee may request or self-enable AI features within company Slack; the Slack administrator denies and logs all such requests. *[Basis: Company Slack AI features are administratively disabled per current configuration; outside counsel confirmed that inputting customer data into third-party AI services violates existing DPA terms.]*

---

## Enforcement

1. The discovering employee or reviewer reports any suspected violation to the violating employee's direct manager immediately upon discovery.
2. The manager notifies Legal immediately when the violation involves customer data.
3. A confirmed violation results in revocation of AI tool access, enforced by Engineering leadership through existing GitHub Copilot seat controls and Slack administrator controls.
4. For employees without AI tool access to revoke—including sales staff using personal or free-tier tools—a confirmed violation results in written notice placed in the employee's existing HR file and a mandatory manager review within five business days.
5. Managers document all confirmed violations in the employee's existing HR file, which constitutes the official violation log.