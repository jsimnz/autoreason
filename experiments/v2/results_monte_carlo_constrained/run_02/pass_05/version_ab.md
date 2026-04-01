# AI Tool Usage Policy
**Effective Date:** [DATE — must be populated before distribution] | **Owner:** Chief Technology Officer | **Audience:** All Employees, Contractors, and Interns

An informal survey found 73% of engineers and 45% of sales staff already use AI tools for work tasks. Three incidents in the past quarter confirm the need for binding rules, effective immediately.

---

## Scope

1. This policy binds all employees, contractors, and interns performing work on behalf of the company.
2. This policy covers all AI tools used for any work-related task, including code assistants, text generators, and chat interfaces.

---

## Permitted Uses

1. Engineers with assigned seats may use GitHub Copilot Business, allocated by Engineering Leads via GitHub admin controls.
2. Engineers may use AI-assisted code generation only when the committing engineer reviews and accepts ownership of every line before commit.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data—including database schemas, records, or identifiers—into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel DPA finding; SOC2 Type II and GDPR obligations)*
2. **No unverified AI-generated content in outbound communications.** Publishing or sending AI-generated text without confirming it contains no third-party copyrighted material is prohibited. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No AI-generated code committed without license review.** Committing AI-generated code containing open-source license artifacts is prohibited. *(Incident 3: intern committed code with a GPL header from AI training data; outside counsel copyright finding)*
4. **No unapproved AI tools for work purposes.** Using any AI service other than GitHub Copilot Business is prohibited. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding)*
5. **No GitHub Copilot Business on FedRAMP-scoped workstreams** until the CTO issues written authorization to Engineering Leads confirming FedRAMP authorization is obtained. *(FedRAMP authorization pending Q3 target)*

---

## Enforcement

1. HR distributes this policy and collects signed acknowledgments before the effective date; no covered individual may use any AI tool for work until acknowledgment is on file.
2. Engineering Leads verify compliance during existing pull request and code review workflows; violations are referred to HR for disciplinary action.
3. Violations involving customer data (Prohibited Use #1) are escalated immediately to Legal and treated as a data incident under the existing SOC2 incident response process.
4. Engineering Leads flag license artifacts during code review (Prohibited Use #3) and escalate to Legal.
5. Engineering Leads enforce the FedRAMP prohibition (Prohibited Use #5) by excluding GitHub Copilot Business from FedRAMP-scoped repositories via existing repository access controls until written CTO authorization is received.
6. GitHub admin controls enforce seat allocation and access revocation for all GitHub Copilot Business usage within the $50K annual AI tooling budget, administered by the CTO.
7. IT maintains Slack AI features in their currently disabled state via existing Slack administrative controls.