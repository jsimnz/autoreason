# AI Tool Usage Policy
**Effective Date:** 2025-07-14 | **Owner:** CTO | **Audience:** All Employees, Contractors, and Interns

---

## Scope

1. This policy applies to all employees, contractors, and interns using any AI tool for any work-related task, on company or personal devices.
2. This policy covers AI-assisted code generation, text generation, and conversational AI interfaces.

---

## Permitted Uses

1. Engineers may use GitHub Copilot Business only after an Engineering Lead assigns them one of the 80 licensed seats via GitHub admin controls; engineers without an assigned seat may not use GitHub Copilot Business.
2. AI-assisted code may be committed only after an Engineering Lead approves the pull request and confirms no open-source license headers or identifiers introduced by the AI tool are present.
3. Sales staff may use AI tools to draft outbound communications only after a Sales Manager reviews and approves the content through the existing outbound communication approval workflow.
4. Additional AI tools may be approved against the $50K annual AI tooling budget; requests are submitted to the CTO, who approves or denies in writing before use begins.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data—including database schemas, records, or identifiers—into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel DPA finding; SOC2 Type II and GDPR obligations)*
2. **No unreviewed AI-generated content in outbound communications.** Sending or publishing AI-generated text not approved by a Sales Manager through the outbound communication approval workflow is prohibited. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No AI-generated code committed without Engineering Lead review.** Committing AI-generated code containing open-source license headers or identifiers is prohibited. *(Incident 3: intern committed code with a GPL header from AI training data; outside counsel finding that AI-generated code may not be copyrightable)*
4. **No unapproved AI tools.** Using any AI service not approved under Permitted Use #4 is prohibited. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding; SOC2 Type II and GDPR obligations; pending FedRAMP authorization Q3 target imposes strict data-handling requirements on all tooling in use before authorization)*
5. **No enabling of Slack AI features.** Re-enabling Slack AI features by any means is prohibited. *(Slack AI features are currently disabled as an existing company control)*

---

## Enforcement

1. Engineering Leads verify compliance with Prohibited Use #3 during existing pull request and code review workflows; violations are referred to HR for disciplinary action.
2. Violations of Prohibited Use #1 are identified through IT's existing SOC2 access-review log audits and escalated immediately to Legal as a data incident under the SOC2 incident response process; confirmed violations are referred to HR for disciplinary action.
3. Sales Managers verify compliance with Prohibited Use #2 by approving all outbound AI-assisted content before sending; violations are referred to HR for disciplinary action.
4. IT enforces Prohibited Uses #4 and #5 through device and browser log audits under the existing SOC2 access-review cadence; confirmed violations are referred to HR for disciplinary action.