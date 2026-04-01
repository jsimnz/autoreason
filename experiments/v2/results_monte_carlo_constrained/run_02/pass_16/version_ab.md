# AI Tool Usage Policy
**Effective Date:** 2025-07-14 | **Owner:** CTO | **Audience:** All Employees and Interns

---

## Scope

1. This policy applies to all employees and interns using any AI tool for any work-related task.
2. This policy governs AI tool use in the context of SOC2 Type II certification requirements, GDPR obligations for EU customers, and the pending FedRAMP authorization targeted for Q3, each of which independently constrains how AI tools may interact with company and customer data.

---

## Permitted Uses

1. Engineers may use GitHub Copilot Business only after an Engineering Lead assigns them one of the 80 licensed seats via GitHub admin controls; engineers without an assigned seat may not use GitHub Copilot Business.
2. AI-generated code may be committed only after an Engineering Lead approves the pull request, confirming the code is reviewed for quality and that no open-source license headers or identifiers introduced by the AI are present.
3. No company-licensed AI tool is currently approved for sales drafting. Sales staff may not use external AI tools to draft outbound communications until a tool is approved by the CTO and documented under this policy.
4. Additional AI tools may be approved against the $50K annual AI tooling budget; requests are submitted to the CTO, who approves or denies before use begins.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data — including database schemas, records, or identifiers — into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms; SOC2 Type II and GDPR obligations)*
2. **No unapproved AI-generated content in outbound communications.** Sending AI-generated text in outbound communications is prohibited until a tool is approved per Permitted Use #3. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No AI-generated code committed without Engineering Lead review.** Committing any AI-generated code without Engineering Lead pull-request approval is prohibited. *(Incident 3: intern committed code with a GPL license header from AI training data; outside counsel finding that AI-generated code may not be copyrightable)*
4. **No unapproved AI tools.** Using any AI service not listed under Permitted Uses is prohibited. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding; SOC2 Type II certification and GDPR obligations govern all tooling handling company data)*

---

## Enforcement

1. Engineering Leads verify compliance with Prohibited Use #3 during existing pull request and code review workflows; violations are referred to HR for disciplinary action.
2. IT identifies violations of Prohibited Use #1 through network and endpoint access-log reviews conducted under the existing SOC2 access-review cadence; confirmed violations are escalated to Legal as a data incident and referred to HR for disciplinary action.
3. Sales Managers verify compliance with Prohibited Use #2 by reviewing outbound communications flagged during normal supervisory oversight; violations are referred to HR for disciplinary action.
4. IT enforces Prohibited Use #4 through device and browser log audits under the existing SOC2 access-review cadence; confirmed violations are referred to HR for disciplinary action.