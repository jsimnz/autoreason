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
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files and contexts that do not involve customer PII, financial data, database schemas, or code that references, queries, or models such data.
3. All AI-generated code must be reviewed by a human engineer before commit. Reviewers must confirm output contains no third-party license notices before approving the pull request.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: Incident #1 — engineer pasted customer database schema into ChatGPT; outside counsel flagged DPA violation risk; GDPR obligations for EU customers; pending FedRAMP authorization.)*
2. **No unapproved AI tools.** Using any AI tool not listed under Permitted Uses is prohibited for all roles. *(Motivating facts: Incident #2 — sales rep used an unapproved AI tool to draft email copy; outside counsel flagged DPA violation risk from third-party AI services; informal survey confirmed 45% of sales staff and 73% of engineers currently use AI tools, the majority of which are unapproved.)*
3. **No AI-generated content that reproduces third-party copyrighted material.** Employees must not transmit or commit AI-generated text or code containing verbatim third-party copyrighted content. *(Motivating fact: Incident #2 — sales rep transmitted AI-generated text containing a competitor's copyrighted marketing copy verbatim.)*
4. **No committing AI-generated code containing third-party license notices.** *(Motivating facts: Incident #3 — intern committed a GPL license notice sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
5. **No representing AI-generated code as original company IP without documented human authorship review.** AI-generated code may not be represented as original company IP in customer deliverables or contracts without documented human review of each material component. *(Motivating fact: outside counsel flagged that AI-generated code may not be copyrightable.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management within the 80-seat limit.
2. PR approval is the existing gate at which reviewers must confirm no third-party license notices are present in AI-generated code. Approving a non-compliant PR constitutes a policy violation by the reviewer.
3. Suspected violations must be reported to Legal and Security via the existing incident reporting channel within 24 hours of discovery.
4. Any confirmed policy violation results in immediate suspension of AI tool access by IT, pending a written reinstatement or termination decision by the employee's manager and HR.

---

**Changes made and problems addressed:**

- **Scope Item 3** rewritten to state only that unapproved tools are prohibited, removing the procurement and budget-governance language. *(Fixes Problem 3.)*
- **Permitted Use Item 2** extended to cover code that references, queries, or models customer data, not only files that contain it directly. *(Fixes Problem 7.)*
- **Prohibited Use #2** motivating-fact parenthetical revised to remove Incident #1 as a cited fact and replace it with Incident #2 and the informal survey findings, which directly support the prohibition on unapproved tools. *(Fixes Problem 4.)*
- **Enforcement Item 3** replaced the manager one-on-one review cadence — which is not an existing process established by the base facts — with a requirement to report suspected violations through the existing incident reporting channel, which is an existing process referenced elsewhere in the document. *(Fixes Problem 5.)*
- **Problem 6 (no enforcement mechanism for sales):** The base facts provide no approved tool for sales and no existing access control covering sales AI usage. No addition can be made without introducing facts not derivable from the base facts. The prohibition on unapproved tools applies to sales on the same terms as all other roles; violations are reportable through the existing incident reporting channel under Enforcement Item 3, which is the only existing process the base facts support for this population.
- **Self-review block** retained only in this revision note section, which is outside the memo body. The memo body above is the complete deliverable. *(Fixes Problem 2.)*
- **Word count:** The policy memo body (Scope through Enforcement) is within 500 words. *(Fixes Problem 1.)*