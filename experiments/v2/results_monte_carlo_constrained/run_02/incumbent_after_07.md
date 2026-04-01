# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** CTO | **Audience:** All Employees, Contractors, and Interns

---

## Scope

1. This policy applies to all employees, contractors, and interns using any AI tool for any work-related task, on company or personal devices.
2. All covered individuals are subject to all Permitted Uses and all Prohibited Uses.
3. This policy covers AI-assisted code generation, text generation, and conversational AI interfaces.

---

## Permitted Uses

1. Engineers with assigned seats may use GitHub Copilot Business, allocated by Engineering Leads via GitHub admin controls.
2. AI-assisted code generation is permitted only when an Engineering Lead approves the pull request containing that code before merge, confirming the committing engineer is the author of record.
3. Employees in non-engineering roles may use AI tools only when those tools are explicitly approved in writing by the CTO and listed in this policy; no such tools are currently approved.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data—including database schemas, records, or identifiers—into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel DPA finding; SOC2 Type II and GDPR obligations)*
2. **No unverified AI-generated content in outbound communications.** Sending or publishing AI-generated text without confirming it contains no third-party copyrighted material is prohibited. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No AI-generated code committed without legal review.** Committing AI-generated code that contains open-source license artifacts or that has not been reviewed for copyright ownership is prohibited. *(Incident 3: intern committed code with a GPL header from AI training data; outside counsel finding that AI-generated code may not be copyrightable and ownership may not vest in the company)*
4. **No unapproved AI tools for work purposes.** Using any AI service other than GitHub Copilot Business is prohibited for all covered individuals unless the CTO issues written approval. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding)*
5. **No GitHub Copilot Business on FedRAMP-related work** until the CTO issues written designation of in-scope work and confirms FedRAMP authorization is obtained. *(FedRAMP authorization pending Q3 target)*
6. **No use of Slack AI features.** Enabling or using AI features within the company Slack instance is prohibited. *(Slack AI features are currently disabled; enabling them would constitute use of an unapproved AI service under Prohibited Use #4)*

---

## Enforcement

1. Engineering Leads verify compliance during existing pull request and code review workflows; violations are referred to HR for disciplinary action.
2. Violations involving customer data (Prohibited Use #1) are escalated immediately to Legal and treated as a data incident under the existing SOC2 incident response process.
3. Engineering Leads flag license artifacts and copyright ownership gaps during code review (Prohibited Use #3) and escalate to Legal.
4. Engineering Leads enforce the FedRAMP prohibition (Prohibited Use #5) by withholding GitHub Copilot Business access from any work the CTO has not designated and authorized in writing.
5. GitHub admin controls enforce seat allocation and access revocation for all GitHub Copilot Business usage.
6. IT maintains Slack AI features in their currently disabled state via existing Slack administrative controls (Prohibited Use #6).