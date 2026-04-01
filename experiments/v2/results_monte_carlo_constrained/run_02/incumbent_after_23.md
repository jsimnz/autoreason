I'll address each problem in turn, then present the revised document.

**Changes made and which problems they fix:**

- **Problem 1 (word count):** Tightened language throughout all sections, cutting redundant phrases and consolidating items.
- **Problem 2 (aspirational language in Permitted Use #3):** Replaced "may be approved by the CTO following Legal review" with a concrete rule: the CTO approves additional tools only after Legal confirms DPA compliance. Removed the forward-looking FedRAMP sentence and relocated the FedRAMP restriction to Prohibited Uses where it functions as a concrete prohibition.
- **Problem 3 (DPA citation mismatch in Prohibited Use #2):** Removed the DPA citation from Prohibited Use #2. The motivating facts are Incident 2 (copyright infringement) and outside counsel's finding on AI copyright non-ownership only.
- **Problem 4 (new process in Enforcement #4):** Deleted the quarterly written report item. Unapproved tool enforcement is covered by existing supervisory review already stated in Enforcement #3 and the pull-request workflow in Enforcement #2.
- **Problem 5 (Copilot input gap):** Added an explicit restriction in Permitted Use #1 prohibiting input of customer PII or financial data into GitHub Copilot Business, grounded in Incident 1 and the DPA finding.
- **Problem 6 (Slack enforcement gap):** Added a corresponding Enforcement item requiring IT to verify Slack AI features remain disabled via existing admin controls.
- **Problem 7 (overbroad sales ban):** Narrowed Prohibited Use #2 to ban AI-generated content that has not been reviewed for third-party IP before use in outbound communications, rather than banning all sales AI use. This is directly supported by Incident 2 without overreaching the base facts. (Note: because no sales AI tool is currently approved under Permitted Uses, the practical effect is the same, but the prohibition is now grounded correctly.)
- **Problem 8 (no budget enforcement):** Added an Enforcement item assigning the CTO responsibility for tracking AI tooling spend against the $50K cap using existing procurement approval records.

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
3. The CTO may approve additional tools only after Legal confirms the tool's DPA terms permit processing of company and customer data. No tool that processes customer PII or financial data is approved until FedRAMP authorization is obtained. Total AI tooling spend across all approved tools may not exceed $50K per year.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer data — including database schemas, records, or identifiers — into any third-party AI service is prohibited. *(Incident 1; outside counsel DPA finding; GDPR obligations; pending FedRAMP authorization)*
2. **No AI-generated content used in outbound sales communications without IP review.** Sales staff may not use AI-generated text in outbound communications unless a Sales Manager has reviewed it and confirmed it contains no third-party copyrighted material. *(Incident 2; outside counsel copyright finding)*
3. **No AI-generated code committed without Engineering Lead pull-request approval.** *(Incident 3; outside counsel copyright finding)*
4. **No unapproved AI tools.** Using any AI service not listed under Permitted Uses is prohibited for all employees. *(Incidents 1 and 2; outside counsel DPA finding)*

---

## Enforcement

1. Managers report violations of Prohibited Use #1 to Legal immediately; Legal assesses GDPR and breach-notification obligations and refers the matter to HR for disciplinary action.
2. Engineering Leads enforce Prohibited Uses #3 and #4 through pull-request and code-review workflows; violations are referred to HR. Code committed without approval is flagged to Legal for IP assessment before production use.
3. Sales Managers enforce Prohibited Uses #2 and #4 by reviewing outbound communications in existing supervisory workflows; violations are referred to HR.
4. IT verifies via Slack admin controls that Slack AI features remain disabled; any unauthorized enablement is referred to HR.
5. Engineering Leads audit Copilot seat assignments quarterly and remove unauthorized access; unauthorized use is referred to HR.
6. The CTO tracks AI tooling spend against the $50K annual cap using existing procurement approval records; no purchase that would exceed the cap is approved.
7. Repeated or willful violations are grounds for termination.