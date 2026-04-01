# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables.
2. GitHub Copilot Business is the sole currently approved AI tool, with 80 seats allocated to engineers. A $50K annual budget is allocated for additional AI tooling approved per Enforcement item 3.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) may be used for code completion, test generation, and documentation. "Customer data" for purposes of this policy means any PII, financial data, database schemas, or configuration files that identify or are derived from customer environments. Copilot may not be used on files containing customer data as defined here.

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

**Changes made and problems fixed:**

- **Problems 1 and 2:** Removed the Revision Notes section entirely. It is not part of a policy memo and contributed to word count.
- **Problem 3:** Removed the sales grace-period provision. No base fact authorizes continued use of unapproved tools; the 45% usage figure describes current behavior, not a business requirement to continue it.
- **Problem 4:** Added a definition of "customer data" directly in Permitted Uses item 1, making the restriction on Copilot use self-contained and reviewable using existing code review processes.
- **Problem 5:** Removed Enforcement item 5 (annual acknowledgment). It described an administrative act with no enforcement consequence and consumed word count without satisfying the enforcement requirement.
- **Problem 6:** Removed Prohibited Uses item 4 (Copilot output distribution restriction). It created unresolvable ambiguity with the blanket approval of Copilot in Permitted Uses item 1. The copyright risk from outside counsel is addressed by the license-review requirement in Prohibited Uses item 3, which applies to all AI-generated code submissions.