# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy applies to all 200 employees and interns of the company.
2. This policy governs all use of AI-assisted tools for any work-related task, including but not limited to code generation, written communications, and email drafting.
3. The $50K annual AI tooling budget is the ceiling for all AI tool licensing; no AI tool may be procured or expensed outside this budget and the Permitted Uses list.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, allocated within the 80 licensed seats by Engineering leadership.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files containing no customer PII, financial data, or database schemas.
3. All AI-generated code must be reviewed by a human engineer before commit. Reviewers must confirm output contains no third-party license notices before approving the pull request.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: Incident #1: engineer pasted customer database schema into ChatGPT; outside counsel flagged DPA violation risk; GDPR obligations for EU customers; pending FedRAMP authorization.)*
2. **No unapproved AI tools.** Using any AI tool not listed under Permitted Uses is prohibited. This applies to all roles, including the 45% of sales staff currently using AI tools for email drafting, who must cease use of unapproved tools immediately. *(Motivating facts: Incidents #1, #2, and #3 each arose from use of tools outside any approved set; outside counsel flagged DPA violation risk from third-party AI services.)*
3. **No AI-generated written content that reproduces third-party copyrighted material.** Employees must not transmit AI-generated text containing verbatim third-party copyrighted content. *(Motivating fact: Incident #2: sales rep transmitted AI-generated text containing a competitor's copyrighted marketing copy verbatim.)*
4. **No committing AI-generated code containing third-party license notices.** *(Motivating facts: Incident #3: intern committed a GPL license notice sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
5. **No delivering AI-generated code as original company IP without documented human authorship review.** AI-generated code may not be represented as original company IP in customer deliverables or contracts without documented human review of each material component. *(Motivating fact: outside counsel flagged that AI-generated code may not be copyrightable.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management within the 80-seat limit.
2. PR approval is the existing gate at which reviewers must confirm no third-party license notices are present in AI-generated code; approval of a non-compliant PR constitutes a policy violation by the reviewer.
3. Managers are responsible for auditing direct reports' AI tool use. IT revokes access to unapproved tools upon manager or Legal request using existing access controls.
4. Any policy violation results in immediate suspension of AI tool access by IT, pending a written reinstatement or termination decision by the employee's manager and HR.
5. All incidents must be reported to Legal and Security via the existing incident reporting channel.

---

**Changes made and problems addressed:**

- **Problem 1 & 2:** Removed the preamble and changelog entirely. The document is now the memo. Word count is within 500 words.
- **Problem 3:** Replaced Scope item 3 with a statement about the $50K budget constraint, which is a genuine scoping boundary on tool procurement. This also fixes Problem 5.
- **Problem 4:** Added explicit language in Prohibited Use #2 naming sales staff and their current AI email-drafting practice, satisfying the "use ALL base facts" constraint.
- **Problem 5:** Addressed via the new Scope item 3 referencing the $50K budget fact.
- **Problem 6:** Removed the Slack AI prohibition entirely. The base facts state Slack AI is already disabled by IT administrator controls; there is no employee-facing action to prohibit. The compliance posture is maintained by the existing IT control, not by a policy instruction to employees.
- **Problem 7:** Rewrote Enforcement item 2 to frame PR approval as the existing gate mechanism rather than a novel attestation requirement, and to specify that approving a non-compliant PR is itself a violation.
- **Problem 8:** Added "by IT" to Enforcement item 4, designating the actor responsible for executing access suspension.