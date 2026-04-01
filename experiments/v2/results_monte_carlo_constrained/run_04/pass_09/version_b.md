I'll address each problem before presenting the revised document.

**Changes made and which problems they fix:**

- **Problem 1 (document is not a memo):** Removed the entire revision commentary block. The deliverable is now the policy memo only.
- **Problem 2 (word count):** Compressed motivating-fact citations throughout Prohibited Uses, shortened Enforcement items, and removed redundant phrasing. Policy body is approximately 430 words.
- **Problem 3 (Prohibited Use #3 duplicates Permitted Use #4):** Removed Prohibited Use #3. The review requirement already appears in Permitted Use #4; restating it as a prohibition was redundant. Renumbered remaining prohibitions.
- **Problem 4 (Permitted Use #4 authorizes unapproved tools):** Rewrote Permitted Use #4 to authorize only tools specifically approved by Legal in writing before first use, and added that Legal maintains a published approved-tools list. This resolves the circularity: a tool becomes permitted upon Legal approval, which is a named mechanism rather than a forward reference to a nonexistent list.
- **Problem 5 (24-hour timeframe not derivable from base facts):** Removed the 24-hour window and associated late-reporting penalty. Enforcement item 4 now requires prompt reporting via the existing incident reporting channel with no invented timeframe.
- **Problem 6 (revert obligation has no named responsible party):** Assigned the revert obligation explicitly to the PR approver's Engineering manager.
- **Problem 7 (Scope item 2 lists unsupported categories):** Removed "AI chat interfaces" as a standalone category. Replaced with language grounded in the base facts: tools that accept text input and return AI-generated output, which covers the ChatGPT incident without inventing a category. Removed "AI features embedded in existing platforms" as a scope category since the only instance (Slack) is already handled by a specific prohibition.

---

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
4. Sales staff may use AI writing tools for email drafting only if Legal has approved the specific tool in writing before first use. Legal maintains and publishes the current approved-tools list. All AI-generated text must be reviewed and edited by the authoring employee before transmission.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: DPA violation risk; GDPR obligations; pending FedRAMP authorization; Incident #1.)*
2. **No unapproved AI tools.** Using any AI tool not listed as approved under Permitted Uses is prohibited. *(Motivating facts: Incidents #1, #2, and #3; DPA violation risk from unapproved third-party services.)*
3. **No committing AI-generated code containing third-party license notices.** *(Motivating facts: Incident #3: GPL license notice sourced from AI training data; outside counsel flagged AI-generated code may not be copyrightable.)*
4. **No employee may request or self-enable Slack AI features.** *(Motivating fact: approved tool list specifies Slack with AI features disabled; IT maintains this state through existing administrator controls.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management within the 80-seat limit.
2. Pull request approval constitutes the reviewer's attestation that no third-party license notices are present. Where a merged PR is found to contain such notices, the approving engineer's Engineering manager is responsible for executing an immediate revert.
3. Any policy violation results in immediate suspension of AI tool access for the offending employee. The employee's manager and HR must issue a written reinstatement or termination decision within 5 business days. A second violation initiates termination review. This track applies to all employees regardless of role.
4. All incidents must be reported to Legal and Security promptly via the existing incident reporting channel.