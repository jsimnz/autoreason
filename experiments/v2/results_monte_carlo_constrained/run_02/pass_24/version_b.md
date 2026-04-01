**Changes made and problems fixed:**

- **Problems 1 and 6:** Deleted the entire preamble. The document now opens directly with the policy memo header.
- **Problem 2:** Removing the preamble eliminates the word-count overrun. The policy text remains within 500 words.
- **Problem 3:** Split Permitted Use #3 into three separate numbered items (#3, #4, #5), each containing a single distinct obligation.
- **Problem 4:** Replaced "Managers" in Enforcement #1 with "the employee's direct supervisor," which applies to all 200 employees regardless of function and requires no new process.
- **Problem 5:** Deleted Prohibited Use #3. The pull-request requirement is already stated as a condition in Permitted Use #2; restating it as a prohibition added no independent content.

---

# AI Tool Usage Policy
**Effective Date:** 2025-07-14 | **Owner:** CTO | **Audience:** All Employees and Interns

---

## Scope

1. This policy governs all work-related AI tool use by all employees and interns across all functions.
2. "Approved tools" means tools explicitly listed under Permitted Uses; all other AI services are unapproved.
3. Company Slack AI features are disabled; employees may not enable them.
4. This policy is enforced through existing access controls, pull-request workflows, and supervisory review processes.

---

## Permitted Uses

1. Engineers may use GitHub Copilot Business after an Engineering Lead assigns them one of the 80 licensed seats via GitHub admin controls. Customer PII and financial data may not be submitted as input to Copilot. *(Incident 1; outside counsel DPA finding)*
2. AI-generated code may be committed only after an Engineering Lead approves the pull request, confirming no open-source license headers are present and documenting the code as AI-generated for IP-ownership tracking. *(Incident 3; outside counsel copyright finding)*
3. The CTO may approve additional tools only after Legal confirms the tool's DPA terms permit processing of company and customer data.
4. No tool that processes customer PII or financial data is approved until FedRAMP authorization is obtained. *(Pending FedRAMP authorization; outside counsel DPA finding)*
5. Total AI tooling spend across all approved tools may not exceed $50K per year.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer data — including database schemas, records, or identifiers — into any third-party AI service is prohibited. *(Incident 1; outside counsel DPA finding; GDPR obligations; pending FedRAMP authorization)*
2. **No AI-generated content used in outbound sales communications without IP review.** Sales staff may not use AI-generated text in outbound communications unless a Sales Manager has reviewed it and confirmed it contains no third-party copyrighted material. *(Incident 2; outside counsel copyright finding)*
3. **No unapproved AI tools.** Using any AI service not listed under Permitted Uses is prohibited for all employees. *(Incidents 1 and 2; outside counsel DPA finding)*

---

## Enforcement

1. The employee's direct supervisor reports violations of Prohibited Use #1 to Legal immediately; Legal assesses GDPR and breach-notification obligations and refers the matter to HR for disciplinary action.
2. Engineering Leads enforce Prohibited Use #3 through pull-request and code-review workflows; violations are referred to HR. Code committed without approval is flagged to Legal for IP assessment before production use.
3. Sales Managers enforce Prohibited Uses #2 and #3 by reviewing outbound communications in existing supervisory workflows; violations are referred to HR.
4. IT verifies via Slack admin controls that Slack AI features remain disabled; any unauthorized enablement is referred to HR.
5. Engineering Leads audit Copilot seat assignments quarterly and remove unauthorized access; unauthorized use is referred to HR.
6. The CTO tracks AI tooling spend against the $50K annual cap using existing procurement approval records; no purchase that would exceed the cap is approved.
7. Repeated or willful violations are grounds for termination.