I'll address each problem, then present the revised document.

**Changes made and which problems they fix:**

- **Removed the preamble/changelog entirely** — fixes *Problem 2*.
- **Removed Scope item 3's prohibition clause**; moved the Slack disablement rule with motivating fact citation to Prohibited Uses as item 5 — fixes *Problem 3* and *Problem 8*.
- **Moved the 80-seat enforcement mechanism** from Permitted Uses item 1 to Enforcement as item 2 — fixes *Problem 4*.
- **Replaced Permitted Uses item 4** (approval process/restriction) with a permitted use for sales employees — fixes *Problem 5* and *Problem 9*.
- **Replaced Enforcement item 4's "aggravating factors" language** with a concrete action: failure to report results in an additional formal disciplinary step — fixes *Problem 6*.
- **Removed the survey statistic** from Prohibited Uses item 2's motivating fact citation; retained only the DPA violation flag — fixes *Problem 7*.
- **Trimmed throughout** to reach the 500-word maximum — fixes *Problem 1*.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI-assisted tools by all 200 employees, including interns, for any work-related task.
2. This policy covers AI coding assistants, AI writing tools, AI chat interfaces, and AI features embedded in existing platforms.
3. This policy supersedes all prior informal practices. No undocumented use constitutes permission.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, allocated by Engineering leadership within the 80 licensed seats.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files containing no customer PII, financial data, or database schemas.
3. All AI-generated code must be reviewed by a human engineer before commit. Reviewers must confirm output contains no third-party license headers before approving.
4. Sales employees may use AI writing assistance only through tools explicitly approved under item 1 or through a future approved tool; all AI-drafted external communications must be reviewed and edited by the authoring employee before sending.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: SOC2 Type II certification obligations; GDPR obligations for EU customers; outside counsel flagged that inputting customer data into third-party AI services likely violates existing DPA terms; Incident #1: engineer pasted customer database schema into ChatGPT.)*
2. **No unapproved AI tools.** Using any AI tool not approved under this policy is prohibited. *(Motivating fact: outside counsel flagged DPA violations arising from use of unapproved third-party AI services.)*
3. **No unreviewed AI-generated content in external communications.** AI-generated text must be reviewed and edited by the authoring employee before transmission. *(Motivating fact: Incident #2: sales rep transmitted a competitor's copyrighted marketing copy verbatim via AI-generated text.)*
4. **No committing AI-generated code containing third-party license notices.** Commits must not include AI-generated license headers not intentionally authored. *(Motivating facts: Incident #3: intern committed a GPL license header sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
5. **Slack AI features must remain disabled.** No employee or IT administrator enables Slack AI features. *(Motivating facts: SOC2 Type II certification obligations; GDPR obligations for EU customers; outside counsel flagged that inputting customer data into third-party AI services likely violates existing DPA terms.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management.
2. IT denies Copilot access requests that would exceed 80 seats until Engineering leadership reallocates an existing seat.
3. Violations identified during code review trigger immediate access suspension pending review by Engineering leadership.
4. Violations by non-engineering employees are escalated by HR to Legal upon identification.
5. All incidents must be reported to Legal and Security within 24 hours via the existing incident reporting channel. Failure to report before discovery results in a formal written warning issued in addition to any other disciplinary action.