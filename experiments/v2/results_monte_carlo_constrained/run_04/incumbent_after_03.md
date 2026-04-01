# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI-assisted tools by all 200 employees, including interns, for any work-related task.
2. This policy covers AI coding assistants, AI writing tools, AI chat interfaces, and any AI features embedded in existing platforms.
3. This policy supersedes all informal practices, including the current undocumented use of AI coding assistants by 73% of engineers and AI writing tools by 45% of sales employees. Prior undocumented use does not constitute permission.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant. Use is limited to the 80 licensed seats; seat allocation is managed by Engineering leadership.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files that contain no customer PII, financial data, or database schemas.
3. All AI-generated code must be reviewed by a human engineer before commit. Reviewers must verify that output contains no third-party license headers before approving the commit.
4. Additional AI tools may be approved through the $50K annual AI tooling budget. Requests must be submitted to Legal and Engineering leadership for review before any tool is used.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: SOC2 Type II obligations; GDPR DPA terms flagged by outside counsel; Incident #1: engineer pasted customer database schema into ChatGPT.)*
2. **No unapproved AI tools.** Using any AI tool not approved under this policy is prohibited for all employees, including AI coding tools other than GitHub Copilot Business and any external AI writing tool. *(Motivating facts: 73% of engineers and 45% of sales employees using unapproved tools without authorization; FedRAMP authorization pending Q3 target; outside counsel flagged that inputting data into unapproved third-party AI services likely violates existing DPA terms.)*
3. **No unreviewed AI-generated content in external communications.** AI-generated text in emails or proposals must be reviewed and edited by the authoring employee before sending. *(Motivating facts: Incident #2: sales rep transmitted competitor's copyrighted marketing copy verbatim; outside counsel flagged that AI-generated content carries copyright ownership risk.)*
4. **No committing AI-generated code containing third-party license notices.** Code commits must not contain AI-generated license headers or third-party license notices not intentionally authored. *(Motivating facts: Incident #3: intern committed GPL-licensed header sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management.
2. Violations identified during code review trigger immediate access review by Engineering leadership.
3. Violations by non-engineering employees are escalated by HR to Legal upon identification.
4. Managers address AI tool compliance with direct reports during existing quarterly performance reviews.
5. Incidents must be reported to Legal and Security within 24 hours using the existing incident reporting channel. Incidents discovered without a prior report are treated as aggravating factors in disciplinary review.
6. Violations of any prohibition in this policy are subject to the existing disciplinary process in the Employee Handbook, up to and including termination.