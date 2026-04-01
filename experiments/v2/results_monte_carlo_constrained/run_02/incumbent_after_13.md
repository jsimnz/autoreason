# AI Tool Usage Policy
**Effective Date:** 2025-07-14 | **Owner:** CTO | **Audience:** All Employees, Contractors, and Interns

---

## Scope

1. This policy applies to all employees, contractors, and interns using any AI tool for any work-related task, on company or personal devices.
2. This policy covers AI-assisted code generation, text generation, and conversational AI interfaces.

---

## Permitted Uses

1. Engineers with assigned seats may use GitHub Copilot Business; seats are allocated by Engineering Leads via GitHub admin controls. Engineers without an assigned seat may not use GitHub Copilot Business until a seat is assigned.
2. AI-assisted code may be committed only after an Engineering Lead approves the pull request and confirms the submission contains no open-source license headers or license identifiers introduced by the AI tool.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data—including database schemas, records, or identifiers—into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel DPA finding; SOC2 Type II and GDPR obligations)*
2. **No unapproved AI-generated content in outbound communications.** Sending or publishing AI-generated text that has not been reviewed and approved by a Sales Manager through the existing outbound communication approval workflow is prohibited. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No AI-generated code committed without Engineering Lead review.** Committing AI-generated code containing open-source license headers or identifiers is prohibited. *(Incident 3: intern committed code with a GPL header from AI training data; outside counsel finding that AI-generated code may not be copyrightable)*
4. **No unapproved AI tools for work purposes.** Using any AI service not listed in Permitted Uses is prohibited. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding; SOC2 Type II, GDPR obligations, and pending FedRAMP authorization)*
5. **No enabling of Slack AI features.** Re-enabling Slack AI features by any means for any work purpose is prohibited. *(Slack AI features are currently disabled as a company control; outside counsel DPA finding applies to any third-party AI data pathway; SOC2 Type II and GDPR obligations)*

---

## Enforcement

1. Engineering Leads verify compliance with Prohibited Use #3 during existing pull request and code review workflows; violations are referred to HR for disciplinary action.
2. Violations involving customer data (Prohibited Use #1) are escalated immediately to Legal and treated as a data incident under the existing SOC2 incident response process. Department managers are responsible for detecting and reporting Prohibited Use #1 violations by their staff before escalation.
3. Sales Managers verify compliance with Prohibited Use #2 by approving all outbound AI-assisted content before sending, using existing outbound communication approval workflows; violations are referred to HR for disciplinary action.
4. IT enforces Prohibited Uses #4 and #5 through device and browser log audits under the existing SOC2 access-review cadence; confirmed violations are referred to HR for disciplinary action.