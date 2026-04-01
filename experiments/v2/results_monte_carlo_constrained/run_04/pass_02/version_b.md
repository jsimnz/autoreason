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

**Changes made and problems addressed:**

- **Problem 1 (word count):** Removed Prohibition 5 (new pre-release disclosure process), Prohibition 6 (Slack), and the tool-request process from Permitted Use 3, and tightened phrasing throughout to bring the document within 500 words.
- **Problem 2 (subjectivity in Permitted Use 4):** Removed the phrase "flagging any code segments intended for customer-facing product delivery for additional IP review," which depended on reviewer interpretation of intent. The reviewer obligation is now limited to the verifiable act of checking for license headers.
- **Problem 3 (marketing materials not in base facts):** Changed "emails, proposals, or marketing materials" to "emails or proposals," which are directly derivable from the base facts (sales AI email drafting, Incident #2).
- **Problem 4 (Prohibition 5 introduced new process):** Removed Prohibition 5 entirely. No existing pre-release Legal disclosure mechanism exists in the base facts.
- **Problem 5 (Slack prohibition unsupported):** Removed Prohibition 6. The base facts state Slack AI features are already disabled at the platform level; no employee-facing prohibition is warranted or enforceable.
- **Problem 6 (invented tool-request process):** Removed the tool request submission process from Permitted Use 3. Replaced with a statement that no external AI writing tool is currently authorized, which is enforceable through existing access controls without creating a new workflow.
- **Problem 7 (Enforcement item 1 was a prose paragraph):** Split Enforcement item 1 into three separate numbered items (1, 2, 3) covering IT provisioning, code review triggers, and non-engineering manager review respectively.
- **Problem 8 (misattributed motivating fact for Prohibition 2):** Removed the copyrightability citation from Prohibition 2. The sole cited motivating fact is now FedRAMP pending authorization, which is the primary driver for restricting unapproved coding tools.