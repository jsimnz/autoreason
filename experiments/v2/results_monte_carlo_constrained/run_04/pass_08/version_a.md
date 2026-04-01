# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI-assisted tools by all 200 employees, including interns, for any work-related task.
2. This policy covers AI coding assistants, AI writing tools, AI chat interfaces, and AI features embedded in existing platforms.
3. This policy supersedes all prior informal practices.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, allocated within the 80 licensed seats by Engineering leadership.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files containing no customer PII, financial data, or database schemas.
3. All AI-generated code must be reviewed by a human engineer before commit. Reviewers must confirm output contains no third-party license headers before approving the pull request.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: outside counsel flagged DPA violations from inputting customer data into third-party AI services; GDPR obligations for EU customers; pending FedRAMP authorization Q3 target; Incident #1: engineer pasted customer database schema into ChatGPT.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses is prohibited. *(Motivating facts: Incidents #1, #2, and #3 each arose from use of tools outside any approved set; outside counsel flagged DPA violations from unapproved third-party AI services.)*
3. **No unreviewed AI-generated content in external communications.** AI-generated text must be reviewed and edited by the authoring employee before transmission. *(Motivating fact: Incident #2: sales rep transmitted a competitor's copyrighted marketing copy verbatim via AI-generated text.)*
4. **No committing AI-generated code containing third-party license notices.** *(Motivating facts: Incident #3: intern committed a GPL license header sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
5. **Slack AI features must remain disabled.** No employee or administrator may enable them. *(Motivating fact: the approved tool list specifies Slack with AI features disabled.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management within the 80-seat limit.
2. Pull request approval constitutes the reviewer's attestation that no third-party license headers are present; approved PRs containing such headers are subject to immediate revert and access suspension.
3. Violations identified during code review trigger immediate access suspension. Engineering leadership must issue a written reinstatement or termination decision within 5 business days.
4. Violations by non-engineering employees are escalated to HR and Legal. HR issues a formal written warning on first violation and initiates termination review on second violation.
5. All incidents must be reported to Legal and Security within 24 hours via the existing incident reporting channel. Failure to report within 24 hours results in a formal written warning in addition to any other disciplinary action.