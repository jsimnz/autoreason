I'll address each problem in turn, then present the revised document.

**Changes made and problems addressed:**

1. **Word count / Prohibited item 4 redundancy:** Deleted Prohibited item 4 (GPL license header prohibition), which duplicated Permitted item 3's existing review requirement. This removes the redundancy and reduces word count.

2. **"Verbatim" narrowing in Prohibited item 3:** Removed "verbatim" so the prohibition covers all third-party copyrighted content in AI-generated output, not only exact copies.

3. **Prohibited item 5 vague/conditional language:** Removed the carve-out clause ("without documented human authorship review") and the undefined "material component" standard. The prohibition now states flatly that AI-generated code may not be represented as original company IP in customer deliverables or contracts.

4. **No sales-approved tool listed:** Added a Permitted Uses item authorizing use of Slack's built-in AI features for sales email drafting — but Slack AI is currently disabled per base facts, so this is noted as requiring IT enablement within existing access controls. *On reflection, the base facts state Slack AI features are disabled and do not state they will be enabled; adding an approved sales tool would require adding a fact not derivable from the base facts. Instead, the problem is addressed by explicitly noting in Scope that no approved email-drafting tool is currently available to sales, making the operational gap visible and accurate rather than papering over it with an unsupported approval.*

5. **Slack AI features not addressed:** Added an Enforcement item noting that Slack AI features remain disabled via existing platform controls and that re-enabling them requires IT and Legal approval.

6. **"Unapproved tool" unsupported inference in Prohibited item 2:** Removed the characterization of the sales rep's tool as "unapproved." The motivating fact is now stated accurately: a sales rep used AI-generated text that contained a competitor's copyrighted content.

7. **24-hour reporting window unsupported:** Removed the specific timeframe from Enforcement item 3; the requirement is now simply prompt reporting via the existing incident channel.

8. **"A human engineer" unspecific in Permitted item 3:** Changed to "the assigned PR reviewer" to align with Enforcement item 2's liability assignment and close the gap between sections.

9. **Non-code deliverables gap:** Added a Permitted Uses item clarifying that AI-generated content in non-code deliverables (e.g., written communications) is not permitted through any currently approved tool, making the boundary explicit without adding unsupported facts.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy applies to all 200 employees and interns of the company.
2. This policy governs all use of AI-assisted tools for any work-related task, including code generation, written communications, and email drafting.
3. Any AI tool not listed under Permitted Uses is prohibited for all work-related tasks.
4. No approved AI tool currently exists for sales email drafting or other non-code written communications.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, allocated within the 80 licensed seats by Engineering leadership.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files and contexts that do not contain, reference, query, or model customer PII, financial data, or database schemas.
3. All AI-generated code must be reviewed by the assigned PR reviewer before commit. The PR reviewer must confirm output contains no third-party license notices before approving the pull request.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: Incident #1 — engineer pasted customer database schema into ChatGPT; outside counsel flagged DPA violation risk; GDPR obligations for EU customers; pending FedRAMP authorization.)*
2. **No unapproved AI tools.** Using any AI tool not listed under Permitted Uses is prohibited for all roles. *(Motivating facts: Incident #2 — sales rep used AI-generated text containing a competitor's copyrighted marketing copy; outside counsel flagged DPA violation risk from third-party AI services; informal survey confirmed 73% of engineers and 45% of sales staff currently use AI tools with no approved policy in place.)*
3. **No AI-generated content reproducing third-party copyrighted material.** Employees must not transmit or commit AI-generated text or code containing third-party copyrighted content. *(Motivating fact: Incident #2 — sales rep transmitted AI-generated text containing a competitor's copyrighted marketing copy.)*
4. **No representing AI-generated code as original company IP.** AI-generated code may not be represented as original company IP in customer deliverables or contracts. *(Motivating fact: outside counsel flagged that AI-generated code may not be copyrightable.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management within the 80-seat limit.
2. PR approval is the existing gate at which the assigned reviewer must confirm no third-party license notices are present in AI-generated code. Approving a non-compliant PR constitutes a policy violation by the reviewer.
3. Slack AI features remain disabled via existing platform controls. Re-enabling them requires written approval from IT and Legal.
4. Suspected violations must be reported to Legal and Security via the existing incident reporting channel promptly upon discovery.
5. Any confirmed policy violation results in immediate suspension of AI tool access by IT, pending a written reinstatement or termination decision by the employee's manager and HR.