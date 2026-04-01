I'll address each problem in turn, then provide the revised document.

**Changes made and which problems they fix:**

- **Problem 1 (word count):** Compressed parenthetical citations to bare references; cut redundant language throughout; removed Scope item 4 (also fixes Problem 7); merged Prohibitions 3 and 4 (also fixes Problem 3); removed Prohibition 5 (also fixes Problem 5). Reduced to under 500 words.
- **Problem 2 ("promptly"):** Replaced "promptly" with "within 24 hours" in Enforcement item 4.
- **Problem 3 (Prohibition 3 thin grounding):** Merged former Prohibition 3 into Prohibition 4 (now Prohibition 3), scoping it to code commits only, where the base facts (Incidents #2 and #3) provide direct grounding. The general content prohibition is no longer needed because all non-Copilot tools are already banned.
- **Problem 4 (Prohibition 2 contradicts Scope):** Deleted Prohibition 2 entirely. Scope item 3 already prohibits all unapproved tools. The sales-specific callout is removed; Scope governs that.
- **Problem 5 (Prohibition 5 not derivable):** Deleted Prohibition 5 entirely.
- **Problem 6 (Slack re-enable process is new):** Replaced the approval-pathway language with a statement that Slack AI features remain disabled via existing platform controls, with no new process invented.
- **Problem 7 (Scope item 4 is a prohibition):** Deleted Scope item 4.
- **Problem 8 (SOC2 never cited):** Added SOC2 Type II as a motivating fact citation in Prohibition 1.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy applies to all 200 employees and interns of the company.
2. This policy governs all use of AI-assisted tools for any work-related task, including code generation, written communications, and email drafting.
3. Any AI tool not listed under Permitted Uses is prohibited for all work-related tasks.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, allocated within the 80 licensed seats by Engineering leadership.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files and contexts that do not contain, reference, query, or model customer PII, financial data, or database schemas.
3. All AI-generated code must be reviewed by the assigned PR reviewer before commit. The PR reviewer must confirm output contains no third-party license notices before approving the pull request.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: Incident #1 — engineer pasted customer database schema into ChatGPT; outside counsel flagged DPA violation risk; GDPR obligations for EU customers; SOC2 Type II certification requirements; pending FedRAMP authorization.)*
2. **No committing AI-generated code containing third-party license notices or reproducing third-party copyrighted material.** Employees must not commit AI-generated code containing third-party license notices or verbatim copyrighted content. *(Motivating facts: Incident #2 — sales rep transmitted AI-generated text containing a competitor's copyrighted marketing copy; Incident #3 — intern committed a GPL license notice sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management within the 80-seat limit.
2. PR approval is the existing gate at which the assigned reviewer must confirm no third-party license notices are present in AI-generated code. Approving a non-compliant PR constitutes a policy violation by the reviewer.
3. Slack AI features remain disabled via existing platform controls.
4. Suspected violations must be reported to Legal and Security via the existing incident reporting channel within 24 hours of discovery.
5. Any confirmed policy violation results in immediate suspension of AI tool access by IT, pending a written reinstatement or termination decision by the employee's manager and HR.