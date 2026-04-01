# AI Tool Usage Policy
**Effective Date:** 2025-07-14 | **Owner:** CTO | **Audience:** All Employees and Interns

---

## Scope

1. This policy governs all use of AI tools for any work-related task by all employees and interns, including the 120 engineers, 30 sales staff, and 50 employees in other functions.
2. "Approved tools" means tools explicitly listed under Permitted Uses; all other AI services are unapproved.
3. Company Slack AI features are disabled and must remain disabled; employees may not enable them.
4. This policy is enforced through existing access controls, pull-request workflows, and supervisory review processes.

---

## Permitted Uses

1. Engineers may use GitHub Copilot Business after an Engineering Lead assigns them one of the 80 licensed seats via GitHub admin controls; unassigned employees may not use it. Customer PII and financial data may not be submitted as input to Copilot. *(Incident 1; outside counsel DPA finding)*
2. AI-generated code may be committed only after an Engineering Lead approves the pull request, confirming no open-source license headers or identifiers introduced by the AI are present, and confirming the code is documented as AI-generated for IP-ownership tracking purposes. *(Incident 3; outside counsel copyright finding)*
3. The CTO may approve additional tools only after Legal confirms the tool's DPA terms permit processing of company and customer data. No tool that processes customer PII or financial data is approved until FedRAMP authorization is obtained. Total AI tooling spend across all approved tools may not exceed $50K per year.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer data — including database schemas, records, or identifiers — into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms; GDPR obligations for EU customers; pending FedRAMP authorization)*
2. **No AI-generated content in outbound sales communications without IP review.** Sales staff may not use AI-generated text in outbound communications unless a Sales Manager has reviewed it and confirmed it contains no third-party copyrighted material. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim; outside counsel copyright finding)*
3. **No AI-generated code committed without Engineering Lead pull-request approval.** *(Incident 3: intern committed code with a GPL license header from AI training data; outside counsel finding that AI-generated code may not be copyrightable)*
4. **No unapproved AI tools.** Using any AI service not listed under Permitted Uses is prohibited for all employees regardless of function. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding)*

---

## Enforcement

1. Managers report violations of Prohibited Use #1 to Legal immediately; Legal assesses notification obligations under GDPR and applicable breach-notification law and refers the violation to HR for disciplinary action.
2. Engineering Leads enforce Prohibited Uses #3 and #4 through existing pull-request and code-review workflows; violations are referred to HR. Any AI-generated code committed without prior approval is flagged to Legal for IP-ownership assessment before use in production.
3. Sales Managers enforce Prohibited Uses #2 and #4 by reviewing outbound communications in existing supervisory workflows; violations are referred to HR.
4. IT verifies via Slack admin controls that Slack AI features remain disabled; any unauthorized enablement is referred to HR.
5. Engineering Leads audit GitHub Copilot Business seat assignments quarterly and remove access for any unassigned user; unauthorized use identified in audit is referred to HR.
6. The CTO tracks AI tooling spend against the $50K annual cap using existing procurement approval records; no purchase that would exceed the cap is approved.
7. Repeated or willful violations are grounds for termination.