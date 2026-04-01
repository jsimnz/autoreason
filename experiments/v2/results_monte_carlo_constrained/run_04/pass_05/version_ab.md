# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI-assisted tools by all 200 employees, including interns, for any work-related task.
2. This policy covers AI coding assistants, AI writing tools, AI chat interfaces, and AI features embedded in existing platforms.
3. This policy supersedes all prior informal practices. Slack AI features are currently disabled; IT controls that setting and must not enable it without Legal and Engineering leadership approval.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, allocated by Engineering leadership within the 80 licensed seats. IT denies access requests that would exceed 80 seats until Engineering leadership reallocates an existing seat.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files containing no customer PII, financial data, or database schemas.
3. All AI-generated code must be reviewed by a human engineer before commit. Reviewers must confirm output contains no third-party license headers before approving.
4. Sales employees may use AI writing assistance only through tools explicitly approved under this policy. All AI-drafted external communications must be reviewed and edited by the authoring employee before sending.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: SOC2 Type II certification obligations; GDPR obligations for EU customers; outside counsel flagged that inputting customer data into third-party AI services likely violates existing DPA terms; Incident #1: engineer pasted customer database schema into ChatGPT.)*
2. **No unapproved AI tools.** Using any AI tool not approved under this policy is prohibited, including AI coding tools other than GitHub Copilot Business and any external AI writing tool. *(Motivating facts: outside counsel flagged DPA violations arising from use of unapproved third-party AI services; Incidents #1, #2, and #3 each involved unapproved or uncontrolled tool use.)*
3. **No unreviewed AI-generated content in external communications.** AI-generated text in emails or proposals must be reviewed and edited by the authoring employee before transmission. *(Motivating fact: Incident #2: sales rep transmitted a competitor's copyrighted marketing copy verbatim via AI-generated text.)*
4. **No committing AI-generated code containing third-party license notices.** Commits must not include AI-generated license headers not intentionally authored. *(Motivating facts: Incident #3: intern committed a GPL license header sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management.
2. Violations identified during code review trigger immediate access suspension pending review by Engineering leadership.
3. Violations by non-engineering employees are escalated by HR to Legal upon identification.
4. All incidents must be reported to Legal and Security within 24 hours via the existing incident reporting channel. Failure to report before independent discovery results in a formal written warning issued in addition to any other disciplinary action.