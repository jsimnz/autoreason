# AI Tool Usage Policy
**Effective Date:** [DATE — must be populated before distribution] | **Owner:** Chief Technology Officer | **Audience:** All Employees, Contractors, and Interns

---

## Scope

1. This policy binds all employees, contractors, and interns performing work on behalf of the company.
2. This policy governs all AI tools used for any work-related task, including code assistants, text generators, and chat interfaces.
3. Individuals who have not signed acknowledgment of this policy are not authorized to use any AI tool for work purposes.

---

## Permitted Uses

1. Engineers may use GitHub Copilot Business seats allocated by Engineering Leads via GitHub admin controls.
2. Engineers may use AI-assisted code generation only when the committing engineer reviews, understands, and accepts ownership of every line before commit.
3. Sales employees may use AI tools to draft outbound content using only non-confidential, non-customer data, with human review completed before sending.
4. AI tooling expenditures are limited to the $50K/year allocated budget, administered by the Chief Technology Officer.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data—including database schemas, records, or identifiers—into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel DPA finding; SOC2 Type II and GDPR obligations)*
2. **No unverified AI-generated content in outbound communications.** Sending or publishing AI-generated text without confirming it contains no third-party copyrighted material is prohibited. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No AI-generated code committed without license review.** Committing AI-generated code containing open-source license artifacts is prohibited. *(Incident 3: intern committed code containing a GPL header from AI training data; outside counsel copyright finding)*
4. **No unapproved AI tools for any work purpose.** Using any AI service other than GitHub Copilot Business for work tasks is prohibited. *(Incidents 1 and 2 involved external third-party services; outside counsel DPA finding)*
5. **No enabling of Slack AI features.** Employees must not enable Slack AI features, which are currently disabled. *(Outside counsel DPA finding; SOC2 Type II and GDPR obligations)*
6. **No GitHub Copilot Business use on FedRAMP-scoped workstreams** until FedRAMP authorization is obtained. *(FedRAMP authorization pending Q3 target)*

---

## Enforcement

1. HR distributes this policy to all covered individuals and collects signed acknowledgments before the effective date; no covered individual may use any AI tool for work purposes until acknowledgment is on file.
2. Engineering Leads verify compliance during existing pull request and code review workflows; violations are referred to HR for disciplinary action.
3. Violations involving customer data (Prohibited Use #1) are escalated immediately to Legal and treated as a potential data incident under the existing SOC2 incident response process.
4. Sales Managers confirm human review of AI-assisted outbound content as a required step in the existing pre-send deal approval workflow before content is transmitted; unconfirmed content is not approved to send.
5. GitHub admin controls enforce seat allocation and access revocation for all GitHub Copilot Business usage.
6. Engineering Leads flag license artifacts during code review (Prohibited Use #3) and escalate to Legal.
7. Engineering Leads enforce the FedRAMP workstream prohibition (Prohibited Use #6) by excluding GitHub Copilot Business from FedRAMP-scoped repositories via existing repository access controls.
8. IT enforces the Slack AI feature prohibition (Prohibited Use #5) via existing Slack administrative controls.