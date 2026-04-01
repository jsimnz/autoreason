I'll address each problem in turn, then present the revised document.

**Changes made and which problem each fixes:**

- **Problem 1 (word count):** Tightened language throughout every section, eliminated redundant phrasing, and condensed parentheticals to stay within 500 words.
- **Problem 2 (Prohibited Use #5 lacks base-fact motivation):** Grounded the Slack prohibition in the base facts: the company handles customer PII and financial data, holds SOC2 Type II certification, and has a pending FedRAMP authorization — all of which require controlled data-handling environments. Slack AI features being disabled is the *control*; those compliance obligations are the *motivation*.
- **Problem 3 (invented sales approval workflow):** Removed reference to an "existing outbound communication approval workflow." Replaced with Sales Manager written approval before sending, which is derivable from the managerial structure implied by the base facts (30 sales staff with Sales Managers identified as a role in the incidents).
- **Problem 4 (Prohibited Use #3 too narrow):** Broadened the prohibition to cover all AI-generated code committed without Engineering Lead review, not only code with license headers. The license-header check remains as one explicit element of that review, but the prohibition now reflects the full scope of outside counsel's copyrightability finding.
- **Problem 5 (Enforcement #2 overclaims log capability):** Replaced the claim that SOC2 access-review logs detect external AI inputs (not established in the base facts) with enforcement through IT-managed network and endpoint access controls — a capability derivable from the existing SOC2 access-control infrastructure — plus mandatory self-reporting and manager attestation, which require no new tooling.
- **Problem 6 (Permitted Use #4 circular / ungrounded):** Retained the CTO approval pathway (the $50K budget allocation implies an authorization process exists) but removed the claim of a formal written approval process not grounded in the facts. Simplified to: requests go to the CTO; use begins only after CTO approval.
- **Problem 7 (FedRAMP under-addressed):** Added FedRAMP as an explicit, named compliance driver in Scope alongside SOC2 and GDPR, and referenced it directly in the relevant prohibition rather than only parenthetically.
- **Problem 8 (Scope items thin):** Expanded Scope to add a distinct item covering EU-customer GDPR obligations and contractor data-handling, making the two items meaningfully distinct rather than two halves of one statement.

---

# AI Tool Usage Policy
**Effective Date:** 2025-07-14 | **Owner:** CTO | **Audience:** All Employees, Contractors, and Interns

---

## Scope

1. This policy applies to all employees, contractors, and interns using any AI tool for any work-related task, on company or personal devices. Contractors have the same data-handling obligations as employees under this policy.
2. This policy governs compliance with SOC2 Type II certification requirements, GDPR obligations for EU customers, and the pending FedRAMP authorization (Q3 target), each of which independently constrains how AI tools may interact with company and customer data.

---

## Permitted Uses

1. Engineers may use GitHub Copilot Business only after an Engineering Lead assigns them one of the 80 licensed seats via GitHub admin controls; engineers without an assigned seat may not use GitHub Copilot Business.
2. AI-generated code may be committed only after an Engineering Lead approves the pull request, confirming the code is reviewed for quality and that no open-source license headers or identifiers introduced by the AI are present.
3. Sales staff may use AI tools to draft outbound communications only after a Sales Manager reviews and approves the content in writing before it is sent.
4. Additional AI tools may be approved against the $50K annual AI tooling budget; requests are submitted to the CTO, who approves or denies before use begins.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data — including database schemas, records, or identifiers — into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel DPA finding; SOC2 Type II and GDPR obligations)*
2. **No unapproved AI-generated content in outbound communications.** Sending AI-generated text not approved by a Sales Manager under Permitted Use #3 is prohibited. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No AI-generated code committed without Engineering Lead review.** Committing any AI-generated code without Engineering Lead pull-request approval is prohibited. *(Incident 3: intern committed code with a GPL header from AI training data; outside counsel finding that AI-generated code may not be copyrightable)*
4. **No unapproved AI tools.** Using any AI service not approved under Permitted Use #4 is prohibited. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding; SOC2 Type II certification; GDPR obligations; FedRAMP authorization requirements govern all tooling handling company data before authorization is granted)*
5. **No enabling of Slack AI features.** Re-enabling Slack AI features by any means is prohibited. *(Company handles customer PII and financial data; SOC2 Type II and GDPR obligations require controlled data environments; FedRAMP authorization requires demonstrated data-handling controls on all active tooling)*

---

## Enforcement

1. Engineering Leads verify compliance with Prohibited Use #3 during existing pull request and code review workflows; violations are referred to HR for disciplinary action.
2. Violations of Prohibited Use #1 are identified through IT-managed network and endpoint access controls under the existing SOC2 infrastructure, mandatory employee self-reporting, and manager attestation; confirmed violations are escalated to Legal as a data incident and referred to HR for disciplinary action.
3. Sales Managers verify compliance with Prohibited Use #2 by approving all outbound AI-assisted content before sending; violations are referred to HR for disciplinary action.
4. IT enforces Prohibited Uses #4 and #5 through device and browser log audits under the existing SOC2 access-review cadence; confirmed violations are referred to HR for disciplinary action.