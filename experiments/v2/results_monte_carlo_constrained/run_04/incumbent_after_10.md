# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI-assisted tools by all 200 employees, including interns, for any work-related task.
2. This policy covers AI coding assistants, AI writing tools, and any tool that accepts employee-provided input and returns AI-generated output.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, allocated within the 80 licensed seats by Engineering leadership.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files containing no customer PII, financial data, or database schemas.
3. All AI-generated code must be reviewed by a human engineer before commit. Reviewers must confirm output contains no third-party license notices before approving the pull request.
4. Sales staff may use AI writing tools only after Legal provides written approval for a specific tool before first use. All AI-generated text must be reviewed and edited by the authoring employee before transmission.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: outside counsel flagged DPA violation risk from inputting customer data into third-party AI services; GDPR obligations for EU customers; pending FedRAMP authorization Q3 target; Incident #1: engineer pasted customer database schema into ChatGPT.)*
2. **No unapproved AI tools.** Using any AI tool not listed as approved under Permitted Uses is prohibited. *(Motivating facts: Incidents #1, #2, and #3 each arose from use of tools outside any approved set; outside counsel flagged DPA violation risk from unapproved third-party AI services.)*
3. **No committing AI-generated code containing third-party license notices.** *(Motivating facts: Incident #3: intern committed a GPL license notice sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
4. **No delivering AI-generated code as company work product without human authorship review.** AI-generated code may not be represented as original company IP in customer deliverables or contracts without documented human authorship of each material component. *(Motivating fact: outside counsel flagged that AI-generated code may not be copyrightable.)*
5. **No employee may request or self-enable Slack AI features.** *(Motivating fact: approved tool list specifies Slack with AI features disabled; IT maintains this state through existing administrator controls.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management within the 80-seat limit.
2. Pull request approval constitutes the reviewer's attestation that no third-party license notices are present.
3. The approving engineer's manager is responsible for executing an immediate revert on any merged PR found to contain third-party license notices.
4. Managers are responsible for auditing direct reports' AI tool use. IT will revoke access to unapproved tools upon manager or Legal request using existing access controls.
5. Any policy violation results in immediate suspension of AI tool access. The employee's manager and HR must issue a written reinstatement or termination decision within 5 business days.
6. All incidents must be reported to Legal and Security within 24 hours via the existing incident reporting channel.