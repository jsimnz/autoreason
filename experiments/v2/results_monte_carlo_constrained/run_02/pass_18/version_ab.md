# AI Tool Usage Policy
**Effective Date:** 2025-07-14 | **Owner:** CTO | **Audience:** All Employees and Interns

---

## Scope

1. This policy governs all use of AI tools for any work-related task by all employees and interns.
2. "Approved tools" means tools explicitly listed under Permitted Uses; all other AI services are unapproved.
3. This policy is enforceable through existing access controls, pull-request workflows, and supervisory review processes. The company holds SOC2 Type II certification, carries GDPR obligations for EU customers, and is pursuing FedRAMP authorization with a Q3 target.

---

## Permitted Uses

1. Engineers may use GitHub Copilot Business only after an Engineering Lead assigns them one of the 80 licensed seats via GitHub admin controls; engineers without an assigned seat may not use GitHub Copilot Business.
2. AI-generated code may be committed only after an Engineering Lead approves the pull request, confirming no open-source license headers or identifiers introduced by the AI are present.
3. Company Slack is approved for work communications; its AI features are disabled and must remain disabled.
4. Additional tools may be approved by the CTO following Legal review of applicable DPA terms; total spend on AI tooling across all approved tools may not exceed $50K per year.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data — including database schemas, records, or identifiers — into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms)*
2. **No AI-generated content in sales outbound communications.** Sales staff may not send AI-generated text in outbound communications unless a tool is approved under Permitted Use #4. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No AI-generated code committed without Engineering Lead review.** Committing AI-generated code without Engineering Lead pull-request approval is prohibited. *(Incident 3: intern committed code with a GPL license header from AI training data; outside counsel finding that AI-generated code may not be copyrightable)*
4. **No unapproved AI tools.** Using any AI service not listed under Permitted Uses is prohibited. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding)*

---

## Enforcement

1. Engineering Leads verify compliance with Prohibited Uses #3 and #4 during existing pull-request and code-review workflows; violations are referred to HR for disciplinary action.
2. Sales Managers verify compliance with Prohibited Uses #2 and #4 by reviewing outbound communications during existing supervisory workflows; violations are referred to HR for disciplinary action.
3. All managers attest quarterly, within the existing SOC2 access-review cadence, that their direct reports are not using unapproved AI tools; confirmed violations are escalated to Legal as a data incident and referred to HR.
4. Repeated or willful violations of any prohibition are grounds for termination and, where customer data is implicated, mandatory notification under SOC2 incident-response procedures.