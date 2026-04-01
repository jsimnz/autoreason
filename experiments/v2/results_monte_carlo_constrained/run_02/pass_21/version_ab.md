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
4. **No unapproved AI tools.** Using any AI service not listed under Permitted Uses is prohibited. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding)*

---

## Enforcement

1. Managers report employees who violate Prohibited Use #1 to Legal immediately; Legal assesses notification obligations under GDPR and applicable breach-notification law, and the violation is referred to HR for disciplinary action.
2. Engineering Leads verify compliance with Prohibited Uses #3 and #4 during existing pull-request and code-review workflows; violations are referred to HR.
3. Sales Managers verify compliance with Prohibited Uses #2 and #4 by reviewing outbound communications during existing supervisory workflows; violations are referred to HR.
4. Managers submit a written quarterly report to the CTO identifying any direct reports observed using unapproved AI tools; confirmed violations are referred by the CTO to HR.
5. Engineering Leads audit GitHub Copilot Business seat assignments quarterly and remove access for any unassigned user; unauthorized use identified in audit is referred to HR.
6. Repeated or willful violations are grounds for termination.

---

**Synthesis rationale by dimension:**

- **Prohibited Use #2 (sales):** Version Y's framing is stronger — stating that no AI tool is currently approved for sales use is more precise and enforceable than Version X's conditional review requirement, which implicitly assumed an approved sales tool existed.
- **Prohibited Use #4 (unapproved tools):** Version X's explicit prohibition is retained. Version Y's argument that Scope makes it implicit is structurally correct but practically weaker; an enforceable policy benefits from an explicit prohibition that managers and HR can cite directly.
- **Enforcement #4 (quarterly oversight):** Version Y's named output — a written report to the CTO — is more concrete and derivable than Version X's SOC2 cadence anchor, which Version X itself flagged as unsupported by the base facts.
- **Enforcement #5 (seat audit):** Version Y's addition is adopted in full. Version X had no enforcement mechanism for Permitted Use #1's seat-assignment requirement, leaving a gap.
- **Enforcement #2:** Version X's broader citation of Prohibited Uses #3 and #4 is retained, since Engineering Leads are best positioned to catch unapproved tool use during code review.
- **Scope and Permitted Uses:** Identical across both versions; retained verbatim.