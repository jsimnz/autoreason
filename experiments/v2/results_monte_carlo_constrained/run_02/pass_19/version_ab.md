# AI Tool Usage Policy
**Effective Date:** 2025-07-14 | **Owner:** CTO | **Audience:** All Employees and Interns

---

## Scope

1. This policy governs all use of AI tools for any work-related task by all employees and interns.
2. "Approved tools" means tools explicitly listed under Permitted Uses; all other AI services are unapproved.
3. This policy is enforceable through existing access controls, pull-request workflows, and supervisory review processes.

---

## Permitted Uses

1. Engineers may use GitHub Copilot Business after an Engineering Lead assigns them one of the 80 licensed seats via GitHub admin controls; unassigned employees may not use it.
2. AI-generated code may be committed only after an Engineering Lead approves the pull request, confirming no open-source license headers or identifiers introduced by the AI are present.
3. Company Slack is approved for work communications; its AI features are disabled and must remain disabled.
4. Additional tools may be approved by the CTO following Legal review of applicable DPA terms; total spend on AI tooling across all approved tools may not exceed $50K per year.
5. Sales staff currently using AI for email drafting have 30 days from the effective date to obtain manager attestation that their usage complies with Prohibited Uses #1 and #2; after 30 days, all sales AI usage requires an approved tool under Permitted Use #4.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data — including database schemas, records, or identifiers — into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms; SOC2 Type II data-handling obligations; GDPR obligations for EU customers; pending FedRAMP authorization requiring controlled data handling)*
2. **No unreviewed AI-generated content in sales outbound communications.** Sales staff may not send AI-generated text in outbound communications unless the content has been reviewed by the sender for third-party IP and the tool is approved under Permitted Use #4 or covered by Permitted Use #5. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No AI-generated code committed without Engineering Lead review.** Committing AI-generated code without Engineering Lead pull-request approval is prohibited. *(Incident 3: intern committed code with a GPL license header from AI training data; outside counsel finding that AI-generated code may not be copyrightable)*
4. **No unapproved AI tools.** Using any AI service not listed under Permitted Uses is prohibited. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding)*

---

## Enforcement

1. Engineering Leads verify compliance with Prohibited Uses #3 and #4 during existing pull-request and code-review workflows; violations are referred to HR for disciplinary action.
2. Sales Managers verify compliance with Prohibited Uses #2 and #4 by reviewing outbound communications during existing supervisory workflows; violations are referred to HR for disciplinary action.
3. All managers attest quarterly, within the existing SOC2 access-review cadence, that their direct reports are not using unapproved AI tools; confirmed violations are escalated to Legal and referred to HR.
4. Repeated or willful violations are grounds for termination; where customer data is implicated, Legal assesses notification obligations under GDPR and applicable breach-notification law.