# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI-assisted tools by all 200 employees, including contractors and interns, for any work-related task.
2. This policy covers AI coding assistants, AI writing tools, AI chat interfaces, and any AI features embedded in existing platforms.
3. This policy supersedes all informal practices. Prior undocumented use does not constitute permission.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant. Use is limited to the 80 licensed seats; seat allocation is managed by Engineering leadership.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on internal or proprietary codebases that contain no customer PII, financial data, or production database schemas.
3. Sales employees may use AI drafting assistance only within tools that do not transmit data to external third-party AI services. No approved external AI writing tool is currently authorized; requests go through the $50K tooling budget approval process with Legal sign-off before use.
4. All AI-generated code must be reviewed by a human engineer before commit. Reviewers are responsible for verifying the output contains no third-party license headers or identifiable open-source snippets.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool (including ChatGPT, Claude, Gemini, or similar) is prohibited. *(Motivating facts: SOC2 Type II obligations, GDPR DPA terms flagged by outside counsel, Incident #1: engineer pasted customer database schema into ChatGPT.)*
2. **No unapproved AI tools for code generation.** Using AI coding tools other than GitHub Copilot Business is prohibited. *(Motivating facts: FedRAMP authorization pending Q3, outside counsel flag on code copyrightability.)*
3. **No unreviewed AI-generated content in customer-facing communications.** AI-generated text in emails, proposals, or marketing materials must be reviewed and edited before sending. *(Motivating fact: Incident #2: sales rep transmitted competitor's copyrighted marketing copy verbatim.)*
4. **No committing AI-generated code without license review.** Code commits must not contain AI-generated license headers or third-party license notices that were not intentionally authored. *(Motivating fact: Incident #3: intern committed GPL-licensed header from AI training data.)*
5. **Slack AI features remain disabled.** Employees must not request or independently enable AI features within company Slack. *(Motivating facts: customer PII and financial data transmitted in Slack channels; DPA compliance risk.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management. Unauthorized tool use identified in code review triggers immediate access review.
2. Violations of Prohibitions 1–5 are subject to the existing disciplinary process outlined in the Employee Handbook, up to and including termination.
3. Managers are responsible for reviewing direct reports' compliance during existing quarterly performance reviews. No new tooling is required.
4. Incidents must be reported to Legal and Security within 24 hours using the existing incident reporting channel. Unreported incidents discovered post-facto are treated as aggravating factors in disciplinary review.