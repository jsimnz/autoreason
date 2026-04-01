# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables.
2. GitHub Copilot Business is the sole currently approved AI tool, with 80 seats allocated to engineers. A $50K annual budget is allocated for additional AI tooling approved per Enforcement item 3.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) may be used for code completion, test generation, and documentation. "Customer data" for purposes of this policy means any PII, financial data, database schemas, or configuration files that identify or are derived from customer environments. Copilot may not be used on files containing customer data as defined here.
2. Sales employees currently using unapproved AI tools for email drafting have a 30-day grace period from the Effective Date to transition to approved tools. During this period, Prohibited Uses item 2 is not enforced against sales employees for email drafting only; all other prohibitions apply in full from the Effective Date.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer PII, financial data, or database schemas into any AI service is prohibited. *(Motivating facts: Incident #1 schema exposure; outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses for any work-related task is prohibited. *(Motivating facts: Incident #2 verbatim copyrighted copy in AI-drafted sales email; outside counsel DPA violation flag; pending FedRAMP authorization.)*
3. **No AI-generated code submitted without license review.** The submitting employee must confirm no third-party license headers or GPL markers are present before submission; pull request reviewers must reject any submission lacking that confirmation. *(Motivating facts: Incident #3 GPL header commit; outside counsel copyright non-ownership flag.)*

---

## Enforcement

1. Violations of Prohibited Uses items 1–2 result in immediate disciplinary action, up to and including termination.
2. Violations of Prohibited Uses item 3 require mandatory remediation — the affected code is reverted or withheld — followed by disciplinary review. Pull request reviewers who approve merges lacking the required license confirmation share accountability and are subject to the same disciplinary review as the submitting employee. Repeated violations result in escalating discipline up to and including termination.
3. Requests to approve new AI tools are submitted to Legal and Security in writing. Approved tools are added to Permitted Uses by written amendment signed by the CEO. No tool is used before that amendment is signed.

---

**Synthesis rationale:** Version Y's inline definition of "customer data" in Permitted Uses item 1 is retained because it makes the Copilot restriction self-contained and reviewable at the file level without new tooling. Version X's 30-day sales grace period is retained as Permitted Uses item 2 because it addresses a foreseeable mass-violation scenario grounded directly in the 45% usage base fact, while preserving full enforcement of all other prohibitions. Version Y's removal of the Copilot external-distribution prohibition is adopted because that restriction created internal conflict with the blanket Copilot approval; the copyright risk is adequately addressed by Prohibited Uses item 3. Version Y's streamlined Enforcement structure is adopted over Version X's five-item version; the annual acknowledgment item described an administrative act rather than an enforcement consequence and was removed.