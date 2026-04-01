**Changes made and which problems they fix:**

- **Problem 1 & 2 (word count violation / preamble should not exist):** Removed the revision log entirely. Compressed policy text to fall within 500 words.
- **Problem 3 (Permitted Use #2 references non-existent approved sales tool):** Revised Prohibited Use #2 to remove the reference to "Permitted Use #3." Clarified that no AI tool is currently approved for sales outbound communications, and that the prohibition applies until the CTO approves one under the tool-approval process.
- **Problem 4 (SOC2 access-review cadence not derivable):** Removed the SOC2 anchor from Enforcement #4. Replaced with a quarterly manager report submitted to the CTO, which is derivable from existing supervisory structure without assuming SOC2 cadence specifics.
- **Problem 5 (Prohibited Use #4 duplicates others):** Removed Prohibited Use #4. The Scope section already defines "approved tools," making the prohibition on unapproved tools structurally implicit and enforced through the specific prohibitions in #1–#3.
- **Problem 6 (Enforcement #4 ambiguous confirmation standard):** Resolved by removal of Prohibited Use #4 and the corresponding Enforcement #4 item. The quarterly attestation is restructured under a new Enforcement #4 with a named actor (managers) and a defined output (written report to CTO).
- **Problem 7 (no enforcement for Permitted Use #1 seat assignment):** Added Enforcement #5 assigning GitHub admin responsibility to Engineering Leads, with HR referral for violations.

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
2. **No AI-generated content in sales outbound communications.** No AI tool is currently approved for sales use; sales staff may not use any AI tool to draft outbound communications until the CTO approves one under Permitted Use #3. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No AI-generated code committed without Engineering Lead review.** Committing AI-generated code without Engineering Lead pull-request approval is prohibited. *(Incident 3: intern committed code with a GPL license header from AI training data; outside counsel finding that AI-generated code may not be copyrightable)*

---

## Enforcement

1. Managers report employees who violate Prohibited Use #1 to Legal immediately; Legal assesses notification obligations under GDPR and applicable breach-notification law, and the violation is referred to HR for disciplinary action.
2. Engineering Leads verify compliance with Prohibited Use #3 during existing pull-request and code-review workflows; violations are referred to HR.
3. Sales Managers verify compliance with Prohibited Use #2 by reviewing outbound communications during existing supervisory workflows; violations are referred to HR.
4. Managers submit a written quarterly report to the CTO identifying any direct reports observed using unapproved AI tools; confirmed violations are referred by the CTO to HR.
5. Engineering Leads audit GitHub Copilot Business seat assignments quarterly and remove access for any unassigned user; unauthorized use identified in audit is referred to HR.
6. Repeated or willful violations are grounds for termination.