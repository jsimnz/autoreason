# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy applies to all 200 employees and interns of the company.
2. This policy governs all use of AI-assisted tools for any work-related task, including code generation, written communications, and email drafting.
3. Tools not listed under Permitted Uses are prohibited. No AI tool may be procured or expensed outside the $50K annual AI tooling budget and the Permitted Uses list.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, allocated within the 80 licensed seats by Engineering leadership.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files containing no customer PII, financial data, or database schemas.
3. All AI-generated code must be reviewed by a human engineer before commit. Reviewers must confirm output contains no third-party license notices before approving the pull request.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: Incident #1: engineer pasted customer database schema into ChatGPT; outside counsel flagged DPA violation risk; GDPR obligations for EU customers; pending FedRAMP authorization.)*
2. **No unapproved AI tools.** Using any AI tool not listed under Permitted Uses is prohibited for all roles. Sales staff currently using AI tools for email drafting must cease use of unapproved tools immediately. *(Motivating facts: Incidents #1, #2, and #3 each arose from use of unapproved tools; outside counsel flagged DPA violation risk from third-party AI services; informal survey confirmed 45% of sales staff currently use unapproved AI tools for email drafting.)*
3. **No AI-generated written content that reproduces third-party copyrighted material.** Employees must not transmit AI-generated text containing verbatim third-party copyrighted content. *(Motivating fact: Incident #2: sales rep transmitted AI-generated text containing a competitor's copyrighted marketing copy verbatim.)*
4. **No committing AI-generated code containing third-party license notices.** *(Motivating facts: Incident #3: intern committed a GPL license notice sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
5. **No delivering AI-generated code as original company IP without documented human authorship review.** AI-generated code may not be represented as original company IP in customer deliverables or contracts without documented human review of each material component. *(Motivating fact: outside counsel flagged that AI-generated code may not be copyrightable.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management within the 80-seat limit.
2. PR approval is the existing gate at which reviewers must confirm no third-party license notices are present in AI-generated code. Approving a non-compliant PR constitutes a policy violation by the reviewer.
3. Managers must review direct reports' AI tool usage at each recurring one-on-one or equivalent check-in and must escalate any suspected violation to Legal and IT within 24 hours of discovery. IT revokes access to unapproved tools upon manager or Legal request using existing access controls.
4. Any policy violation results in immediate suspension of AI tool access by IT, pending a written reinstatement or termination decision by the employee's manager and HR.
5. All incidents must be reported to Legal and Security via the existing incident reporting channel.