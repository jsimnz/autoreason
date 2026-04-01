# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** CTO | **Audience:** All Employees, Contractors, and Interns

An informal survey found 73% of engineers and 45% of sales staff already use AI tools for work tasks. Three incidents in the past quarter exposed data, copyright, and licensing risk. This policy establishes binding rules effective immediately.

---

## Scope

1. Employees, contractors, and interns in engineering roles are subject to Permitted Uses and all Prohibited Uses.
2. Employees, contractors, and interns in sales, operations, and all other non-engineering roles are subject to Prohibited Uses only; no AI tool is approved for their work tasks.
3. This policy covers all AI tools used for any work-related task, including code assistants, text generators, and chat interfaces, regardless of whether the tool is accessed on company or personal devices.

---

## Permitted Uses

1. Engineers with assigned seats may use GitHub Copilot Business, allocated by Engineering Leads via GitHub admin controls.
2. AI-assisted code generation is permitted only when an Engineering Lead approves the pull request containing that code before merge, confirming the committing engineer is the author of record.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data—including database schemas, records, or identifiers—into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel DPA finding; SOC2 Type II and GDPR obligations)*
2. **No unverified AI-generated content in outbound communications.** Sending or publishing AI-generated text without confirming it contains no third-party copyrighted material is prohibited. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No AI-generated code committed without license review.** Committing AI-generated code containing open-source license artifacts is prohibited. *(Incident 3: intern committed code with a GPL header from AI training data; outside counsel copyright finding)*
4. **No unapproved AI tools for work purposes.** Using any AI service other than GitHub Copilot Business is prohibited for all covered individuals. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding)*
5. **No GitHub Copilot Business on FedRAMP-scoped workstreams** until the CTO issues written authorization to Engineering Leads confirming FedRAMP authorization is obtained. *(FedRAMP authorization pending Q3 target)*

---

## Enforcement

1. Current users of any AI tool for work must submit a signed acknowledgment to HR within 5 business days of the effective date; individuals not yet using AI tools must acknowledge before first use. Use continues for current users during this window; it does not for new users.
2. Engineering Leads verify compliance during existing pull request and code review workflows; violations are referred to HR for disciplinary action.
3. Violations involving customer data (Prohibited Use #1) are escalated immediately to Legal and treated as a data incident under the existing SOC2 incident response process.
4. Engineering Leads flag license artifacts during code review (Prohibited Use #3) and escalate to Legal.
5. Engineering Leads enforce the FedRAMP prohibition (Prohibited Use #5) by excluding GitHub Copilot Business from FedRAMP-scoped repositories via existing repository access controls until written CTO authorization is received.
6. GitHub admin controls enforce seat allocation and access revocation for all GitHub Copilot Business usage.
7. IT maintains Slack AI features in their currently disabled state via existing Slack administrative controls.