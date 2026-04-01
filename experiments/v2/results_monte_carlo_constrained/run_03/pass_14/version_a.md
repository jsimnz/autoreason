I'll address each problem, then present only the policy memo.

**Problem 1 & 2 (preamble and word count):** Remove the preamble entirely. The output is the policy memo only.

**Problem 3 (Scope item 3 implies GDPR-only scope):** Rewrite to state that the policy covers all customer PII and financial data. Retain GDPR as a separate, additive obligation rather than a limiting qualifier.

**Problem 4 (Enforcement item 6 reintroduces unsupported disciplinary language):** Remove item 6 entirely.

**Problem 5 (Enforcement item 5 lacks an existing access control mechanism):** Rewrite to ground enforcement in existing controls: managers notify Security and Legal, who document the incident. Remove the ungrounded "revoke access" mechanism for external consumer tools.

**Problem 6 (Prohibited Use 4 parenthetical is inferential):** Replace the causal inference with a direct citation to the base facts: Slack AI features are currently disabled per company configuration, and enabling them constitutes circumvention of an existing access control.

**Problem 7 (no permitted pathway for sales AI use):** Add a Permitted Use item covering sales staff use of AI for drafting, conditioned on manager review before sending, consistent with the constraint already imposed in Prohibited Use 2.

---

**TO:** All Employees, Contractors, and Interns
**FROM:** Office of the CEO
**DATE:** [Date]
**SUBJECT:** AI Tool Usage Policy — Effective Immediately

---

# AI Tool Usage Policy

## Scope

1. Applies to all employees, contractors, and interns across all functions, effective immediately.
2. Covers any use of AI tools for work-related tasks including coding, writing, data analysis, and customer communications.
3. Covers all customer PII and financial data the company handles, regardless of customer location.
4. GDPR obligations apply additionally to all data pertaining to EU customers.

## Permitted Uses

1. **Approved tool — Engineering:** GitHub Copilot Business only. Engineering leadership manages the 80 licensed seats.
2. **Authorized engineering use:** Assigned seat holders may use GitHub Copilot for code suggestions, boilerplate generation, and test writing.
3. **Engineers without an assigned seat** may not use any AI coding tool until a seat is assigned or an alternative tool receives documented CTO and Legal approval.
4. **Authorized sales use:** Sales staff may use AI tools to draft outbound communications only when the sender's manager confirms review for accuracy, originality, and legal compliance in the same thread before the message is sent.
5. **Tool expansion:** Requests for additional AI tools require written approval from CTO and Legal before use begins.

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or customer-identifiable information into any non-approved AI service is prohibited. *(Incident 1 — engineer pasted a customer database schema into ChatGPT; outside counsel finding that doing so violates existing DPA terms; SOC2 Type II certification; GDPR obligations for EU customers.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects unless the sender's manager confirms review for accuracy, originality, and legal compliance in the same thread before sending. *(Incident 2 — sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code committed without license review.** Code produced by AI tools may not be committed unless the pull request reviewer confirms in the PR record that no third-party license headers or GPL-encumbered content are present. *(Incident 3 — intern committed code containing a GPL license header; outside counsel finding that AI-generated code may not be copyrightable.)*
4. **Slack AI features must remain disabled.** Enabling or circumventing the disabled Slack AI features is prohibited. *(Slack AI features are currently disabled per existing company configuration; circumventing that setting overrides an existing access control.)*
5. **No unapproved AI tools.** Using non-approved AI services for work-related tasks without documented CTO and Legal approval is prohibited. *(GitHub Copilot Business is the only assessed tool; unapproved tools have not been reviewed for DPA, SOC2, or GDPR compliance.)*

## Enforcement

1. Violations involving customer data (Prohibited Uses 1, 4) are escalated immediately to Security and Legal for breach assessment.
2. PR reviewers who identify AI-generated code lacking required license confirmation block the merge and notify engineering leadership.
3. Engineering leadership logs the incident before any merge proceeds.
4. Managers whose direct reports trigger Prohibited Use 2 notify Legal and document the incident in the employee's HR file.
5. Managers who identify use of unapproved AI tools or Slack AI circumvention notify Security and Legal, who document the incident.