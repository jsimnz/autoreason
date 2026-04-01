**Changes made and which problems they fix:**

- **Problem 1 & 2 (word count / revision log present):** Removed the revision log. Compressed all citation parentheticals and prose to bring the memo body within 500 words.
- **Problem 3 (30-day provisional window not derivable):** Removed Permitted Use #5 entirely. The base facts do not authorize a grace period or attestation mechanism.
- **Problem 4 (FedRAMP overstated):** Removed FedRAMP from the citation block in Prohibited Use #1. The base fact establishes only that authorization is pending, not that it imposes current obligations.
- **Problem 5 (SOC2 cited without adequate basis):** Removed SOC2 from the citation block in Prohibited Use #1. The base facts do not specify what SOC2 obligations prohibit regarding AI tools.
- **Problem 6 (Prohibited Use #1 not addressed in Enforcement):** Added a dedicated enforcement item for Prohibited Use #1, triggering Legal assessment and HR referral when customer or PII data is implicated.
- **Problem 7 (Permitted Use #3 is a status statement, not a use):** Removed Permitted Use #3. The Slack AI feature status is a constraint, not a permitted AI use.

---

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
3. Additional tools may be approved by the CTO following Legal review of applicable DPA terms; total spend on AI tooling across all approved tools may not exceed $50K per year.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data — including database schemas, records, or identifiers — into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms; GDPR obligations for EU customers)*
2. **No unreviewed AI-generated content in sales outbound communications.** Sales staff may not send AI-generated text in outbound communications unless the content has been reviewed by the sender for third-party IP and the tool is approved under Permitted Use #3. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No AI-generated code committed without Engineering Lead review.** Committing AI-generated code without Engineering Lead pull-request approval is prohibited. *(Incident 3: intern committed code with a GPL license header from AI training data; outside counsel finding that AI-generated code may not be copyrightable)*
4. **No unapproved AI tools.** Using any AI service not listed under Permitted Uses is prohibited. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding)*

---

## Enforcement

1. Managers report employees who violate Prohibited Use #1 to Legal immediately; Legal assesses notification obligations under GDPR and applicable breach-notification law, and the violation is referred to HR for disciplinary action.
2. Engineering Leads verify compliance with Prohibited Uses #3 and #4 during existing pull-request and code-review workflows; violations are referred to HR.
3. Sales Managers verify compliance with Prohibited Uses #2 and #4 by reviewing outbound communications during existing supervisory workflows; violations are referred to HR.
4. All managers attest quarterly, within the existing SOC2 access-review cadence, that their direct reports are not using unapproved AI tools; confirmed violations are escalated to Legal and referred to HR.
5. Repeated or willful violations are grounds for termination.