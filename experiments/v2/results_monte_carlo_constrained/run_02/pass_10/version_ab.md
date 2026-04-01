# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** CTO | **Audience:** All Employees, Contractors, and Interns

---

## Scope

1. This policy applies to all employees, contractors, and interns using any AI tool for any work-related task, on company or personal devices.
2. This policy covers AI-assisted code generation, text generation, and conversational AI interfaces.

---

## Permitted Uses

1. Engineers with assigned seats may use GitHub Copilot Business, allocated by Engineering Leads via GitHub admin controls.
2. AI-assisted code is permitted only when an Engineering Lead approves the pull request, confirming the code has been reviewed for open-source license artifacts and that its copyright status has been assessed by Legal.
3. Employees in non-engineering roles may use an AI tool only when that tool is explicitly approved in writing by the CTO before use. The $50K annual AI tooling budget is allocated for this purpose; no tool is approved without CTO written authorization.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data—including database schemas, records, or identifiers—into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel DPA finding; SOC2 Type II and GDPR obligations)*
2. **No unverified AI-generated content in outbound communications.** Sending or publishing AI-generated text without confirming it contains no third-party copyrighted material is prohibited. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No AI-generated code committed without Engineering Lead and Legal review.** Committing AI-generated code containing open-source license artifacts or unresolved copyright ownership questions is prohibited. *(Incident 3: intern committed code with a GPL header from AI training data; outside counsel finding that AI-generated code may not be copyrightable)*
4. **No unapproved AI tools for work purposes.** Using any AI service not listed as approved in this policy is prohibited. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding; pending FedRAMP authorization requires demonstrable control over all data-handling tools)*
5. **No use of Slack AI features.** AI features in company Slack are disabled and remain prohibited for work use. *(Slack AI features are currently disabled per existing access controls)*

---

## Enforcement

1. Engineering Leads verify compliance with Prohibited Uses #3 and #4 during existing pull request and code review workflows; license artifacts and copyright ownership gaps are escalated to Legal; all violations are referred to HR for disciplinary action.
2. Violations involving customer data (Prohibited Use #1) are escalated immediately to Legal and treated as a data incident under the existing SOC2 incident response process.
3. Sales Managers verify compliance with Prohibited Use #2 during existing outbound communication approval workflows; violations are referred to HR for disciplinary action.
4. IT enforces Prohibited Uses #4 and #5 through device and browser log audits conducted under the existing SOC2 access-review cadence; confirmed violations are referred to HR for disciplinary action.