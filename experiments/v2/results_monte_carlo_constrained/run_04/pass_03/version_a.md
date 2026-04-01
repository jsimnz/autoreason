# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI-assisted tools by all 200 employees, including interns, for any work-related task.
2. This policy covers AI coding assistants, AI writing tools, AI chat interfaces, and any AI features embedded in existing platforms.
3. This policy supersedes all informal practices. Prior undocumented use does not constitute permission.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant. Use is limited to the 80 licensed seats; seat allocation is managed by Engineering leadership.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files that contain no customer PII, financial data, or database schemas.
3. No external AI writing tool is currently authorized for any employee.
4. All AI-generated code must be reviewed by a human engineer before commit. Reviewers must verify that output contains no third-party license headers before approving the commit.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: SOC2 Type II obligations; GDPR DPA terms flagged by outside counsel; Incident #1: engineer pasted customer database schema into ChatGPT.)*
2. **No unapproved AI tools for code generation.** Using AI coding tools other than GitHub Copilot Business is prohibited. *(Motivating fact: FedRAMP authorization pending Q3 target.)*
3. **No unreviewed AI-generated content in external communications.** AI-generated text in emails or proposals must be reviewed and edited by the authoring employee before sending. *(Motivating facts: Incident #2: sales rep transmitted competitor's copyrighted marketing copy verbatim; outside counsel flag that AI-generated content carries copyright ownership risk.)*
4. **No committing AI-generated code containing third-party license notices.** Code commits must not contain AI-generated license headers or third-party license notices not intentionally authored. *(Motivating facts: Incident #3: intern committed GPL-licensed header sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management.
2. Violations identified during code review trigger immediate access review by Engineering leadership.
3. For non-engineering employees, violations are identified through manager review of communications and escalated to Legal and HR.
4. Managers review direct reports' AI tool compliance during existing quarterly performance reviews.
5. Incidents must be reported to Legal and Security within 24 hours using the existing incident reporting channel. Incidents discovered without a prior report are treated as aggravating factors in disciplinary review.
6. Violations of Prohibitions 1–4 are subject to the existing disciplinary process in the Employee Handbook, up to and including termination.

---

**Synthesis rationale by dimension:**

- **Scope:** Identical across both versions; retained verbatim.
- **Permitted Use 3:** Version X's cleaner formulation ("No external AI writing tool is currently authorized") is retained. Version Y's tool-request submission process was removed because it invents a new workflow not supported by existing processes, violating the enforceability constraint.
- **Permitted Use 4:** Version X's narrower reviewer obligation (license header check only) is retained. Version Y's reference to "Prohibition 5" created a circular dependency on a prohibition that is itself removed (see below).
- **Prohibited Uses — count:** Version X's four prohibitions are retained. Version Y's Prohibition 5 (pre-release Legal disclosure) was dropped because no existing pre-release disclosure mechanism appears in the base facts, making it unenforceable without new process. Version Y's Prohibition 6 (Slack) was dropped because Slack AI features are already disabled at the platform level; an employee-facing prohibition adds no enforceable content.
- **Prohibition 2 motivating fact:** Version X's single citation (FedRAMP) is retained. Version Y's addition of the copyrightability flag was removed because that concern motivates Prohibition 4 (license headers in committed code), not the choice of coding tool.
- **Prohibition 3 scope:** Version X's "emails or proposals" is retained over Version Y's inclusion of "marketing materials," which is not directly derivable from the base facts.
- **Prohibition 4 motivating facts:** Both the GPL incident (Incident #3) and the copyrightability flag are cited, as in Version X, because both are directly applicable and Version Y omitted the copyrightability citation without justification.
- **Enforcement structure:** Version X's granular numbered items (six items) are retained over Version Y's consolidated prose-heavy first item, which partially violated the numbered-items constraint and reduced clarity on distinct enforcement mechanisms.