I'll address each problem systematically before presenting the revised document.

**Changes made and which problems they fix:**

- **Problems 1, 7, 8, 9:** Removed the invented 5-business-day timeline (Enforcement #5), removed the "approving engineer's manager" revert responsibility (Enforcement #3 rewritten), and removed the 24-hour reporting SLA (Enforcement #6 rewritten). These cuts also reduce word count toward the 500-word limit.

- **Problems 3 & 4:** Deleted Permitted Use #4 entirely. No AI writing tool for sales is approved in the base facts, and no Legal approval pathway is derivable from them. Sales use of AI writing tools is therefore not a permitted use.

- **Problem 5:** Added a new Prohibited Use directly addressing AI-generated written content that reproduces third-party copyrighted material, citing Incident #2 explicitly.

- **Problem 2:** Rewrote the motivating fact for Prohibited Use #5 (Slack AI) to cite the compliance drivers (SOC2 Type II, GDPR, FedRAMP) as the reasons the tool was disabled, not merely the mechanism.

- **Problem 6:** Rewrote Scope items to be discrete, enforceable scoping statements rather than definitional prose.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy applies to all 200 employees and interns of the company.
2. This policy governs all use of AI-assisted tools for any work-related task.
3. Tools not listed under Permitted Uses are unapproved and subject to Prohibited Uses.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, allocated within the 80 licensed seats by Engineering leadership.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files containing no customer PII, financial data, or database schemas.
3. All AI-generated code must be reviewed by a human engineer before commit. Reviewers must confirm output contains no third-party license notices before approving the pull request.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: Incident #1: engineer pasted customer database schema into ChatGPT; outside counsel flagged DPA violation risk; GDPR obligations for EU customers; pending FedRAMP authorization.)*
2. **No unapproved AI tools.** Using any AI tool not listed under Permitted Uses is prohibited. *(Motivating facts: Incidents #1, #2, and #3 each arose from use of tools outside any approved set; outside counsel flagged DPA violation risk from third-party AI services.)*
3. **No AI-generated written content that reproduces third-party copyrighted material.** Employees must not transmit AI-generated text containing verbatim third-party copyrighted content. *(Motivating fact: Incident #2: sales rep transmitted AI-generated text containing a competitor's copyrighted marketing copy verbatim.)*
4. **No committing AI-generated code containing third-party license notices.** *(Motivating facts: Incident #3: intern committed a GPL license notice sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
5. **No delivering AI-generated code as original company IP without documented human authorship review.** AI-generated code may not be represented as original company IP in customer deliverables or contracts without documented human review of each material component. *(Motivating fact: outside counsel flagged that AI-generated code may not be copyrightable.)*
6. **No enabling Slack AI features.** Employees must not request or self-enable AI features within company Slack. *(Motivating facts: SOC2 Type II certification, GDPR obligations, and pending FedRAMP authorization require controls over data processed by third-party AI services; Slack AI features are disabled by IT administrator controls to maintain these compliance postures.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management within the 80-seat limit.
2. Pull request approval constitutes the reviewer's attestation that no third-party license notices are present in AI-generated code.
3. Managers are responsible for auditing direct reports' AI tool use. IT revokes access to unapproved tools upon manager or Legal request using existing access controls.
4. Any policy violation results in immediate suspension of AI tool access, pending a written reinstatement or termination decision by the employee's manager and HR.
5. All incidents must be reported to Legal and Security via the existing incident reporting channel.