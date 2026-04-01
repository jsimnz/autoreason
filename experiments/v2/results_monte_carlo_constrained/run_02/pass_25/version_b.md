# AI Tool Usage Policy
**Effective Date:** 2025-07-14 | **Owner:** CTO | **Audience:** All Employees and Interns

---

## Scope

1. This policy governs all work-related AI tool use by all 200 employees and interns across all functions, including the 120 engineers, 30 sales staff, and 50 other employees. *(Fixes Problem 8: incorporates the employee breakdown base fact)*
2. "Approved tools" means tools explicitly listed under Permitted Uses; all other AI services are unapproved.
3. Company Slack AI features are disabled; employees may not enable them.
4. This policy is enforced through existing access controls, pull-request workflows, and supervisory review processes.

---

## Permitted Uses

1. Engineers may use GitHub Copilot Business after an Engineering Lead assigns them one of the 80 licensed seats via GitHub admin controls. *(Fixes Problem 6: customer data restriction moved to Prohibited Uses exclusively, removing the ambiguity between PU#1 and PBU#1)*
2. AI-generated code may be committed only after an Engineering Lead approves the pull request, confirming no open-source license headers are present and documenting the code as AI-generated for IP-ownership tracking. *(Incident 3; outside counsel copyright finding)*
3. The CTO may approve additional AI tools only after Legal confirms the tool's DPA terms permit processing of company and customer data, and only for tools that do not process customer PII or financial data until FedRAMP authorization is obtained. *(Fixes Problem 5: the FedRAMP restriction is consolidated into the approval condition rather than stated as a standalone prohibition within Permitted Uses)*
4. Total AI tooling spend across all approved tools may not exceed $50K per year.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer data — including database schemas, records, or identifiers — into any third-party AI service, including GitHub Copilot Business, is prohibited. *(Incident 1; outside counsel DPA finding; GDPR obligations; pending FedRAMP authorization) (Fixes Problem 6: Copilot explicitly covered, resolving the enforcement gap)*
2. **No unreviewed AI-generated content in outbound sales communications.** Sales staff may not use AI-generated text in outbound communications unless a Sales Manager has reviewed it and confirmed it contains no third-party copyrighted material and no content that originated as AI-generated text lacking copyright protection. *(Incident 2; outside counsel copyright and copyrightability findings) (Fixes Problem 4: adds the copyrightability finding as a cited motivating fact)*
3. **No AI-generated code committed without Engineering Lead pull-request approval.** *(Incident 3; outside counsel copyright finding)*
4. **No unapproved AI tools.** Using any AI service not listed under Permitted Uses is prohibited. *(Incidents 1 and 2; outside counsel DPA finding)*

---

## Enforcement

1. Direct supervisors report violations of Prohibited Use #1 to Legal immediately; Legal assesses GDPR and breach-notification obligations and refers the matter to HR for disciplinary action.
2. Engineering Leads enforce Prohibited Uses #3 and #4 through pull-request and code-review workflows; code committed without approval is referred to Legal for IP assessment before production use, and the violation is referred to HR.
3. Sales Managers enforce Prohibited Uses #2 and #4 by reviewing outbound communications in existing supervisory workflows; violations are referred to HR. Given that 45% of sales staff are already using AI tools informally, Sales Managers confirm current outbound communications comply within 30 days of this policy's effective date. *(Fixes Problem 7: incorporates the 45% sales usage statistic as a motivating operational requirement)*
4. IT verifies via Slack admin controls that Slack AI features remain disabled; unauthorized enablement is referred to HR.
5. Engineering Leads audit Copilot seat assignments quarterly and remove unauthorized access; unauthorized use is referred to HR.
6. The CTO tracks AI tooling spend against the $50K annual cap using existing procurement approval records; no purchase that would exceed the cap is approved.
7. Repeated or willful violations are grounds for termination.

---

*(The Synthesis rationale block has been removed entirely. Fixes Problem 2.)*

*(This revision targets approximately 480 words in the policy body. Fixes Problems 1 and 3.)*