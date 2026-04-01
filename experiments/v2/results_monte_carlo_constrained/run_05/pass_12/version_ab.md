# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables.
2. GitHub Copilot Business is the sole approved AI tool, with 80 seats allocated to engineers and managed by the company. The remaining $50K annual AI tooling budget is reserved for tools approved through the process in Enforcement item 5.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) may be used for code completion, test generation, and documentation on non-customer data.
2. Employees whose roles require AI assistance not covered by GitHub Copilot Business (including sales email drafting) may submit a tool request for Legal and Security review under Enforcement item 5.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer PII, financial data, or database schemas into any AI service is prohibited. *(Motivating facts: Incident #1 schema exposure; outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses for any work-related task is prohibited, including AI tools used for sales email drafting. *(Motivating facts: Incident #2 verbatim copyrighted copy in AI-drafted sales email; outside counsel DPA violation flag; pending FedRAMP authorization.)*
3. **No AI-generated code submitted without license review.** The employee submitting a pull request must confirm no third-party license headers or GPL markers are present; pull request reviewers must reject any submission lacking that confirmation. *(Motivating facts: Incident #3 GPL header commit; outside counsel copyright non-ownership flag.)*
4. **No GitHub Copilot output distributed externally without Legal sign-off.** Any externally distributed content that includes GitHub Copilot output requires Legal review before distribution. *(Motivating fact: Outside counsel copyright non-ownership flag for AI-generated code.)*
5. **Slack AI features must remain disabled.** No employee may enable or request enablement of Slack AI features. *(Motivating facts: Outside counsel DPA violation flag for inputting company data into third-party AI services; SOC2 Type II, GDPR, and pending FedRAMP obligations that govern data handling on company platforms.)*

---

## Enforcement

1. Violations of Prohibited Uses items 1–2 (data exposure or unapproved tool use) result in immediate disciplinary action for the responsible employee, up to and including termination.
2. Violations of Prohibited Uses items 3–5 (license, distribution, and platform configuration failures) result in a mandatory remediation step — the affected code or content is reverted or withheld — followed by disciplinary review. Repeated violations result in escalating discipline up to and including termination.
3. Pull request reviewers who approve merges containing unlicensed AI-generated code without confirming compliance share accountability for the violation and are subject to the same disciplinary review as the submitting employee.
4. Compliance with this policy is acknowledged annually by all employees via the existing annual policy acknowledgment process administered by HR.
5. Requests to approve new AI tools are submitted to Legal and Security in writing. Approved tools are added to Permitted Uses by written amendment signed by the CEO. No tool is approved for use before that amendment is signed.

---

**Synthesis rationale:**

- **Scope item 2:** Version X's $50K budget reference is retained; it anchors the approval pathway financially and is a base fact that Version Y leaves unused.
- **Permitted Uses:** Version X's two-item structure is kept over Version Y's, because Version X item 2 provides a defined path for the 45% of sales staff already using AI tools — an unresolved compliance gap Version Y leaves open with no approved alternative. Version Y's item 2 (the customer-data restriction on Copilot) is relocated to where it belongs: Prohibited Uses item 1 already covers it, and a restriction does not belong in Permitted Uses.
- **Prohibited Uses item 2:** Version Y's explicit call-out of sales email drafting is retained because it directly addresses Incident #2 and closes ambiguity for the 45% of sales staff currently using unapproved tools.
- **Prohibited Uses item 5 (Slack):** Version X's citation is used over Version Y's. Version Y's motivating fact is circular (the current configuration motivates the policy that codifies the current configuration). Version X grounds the prohibition in the outside counsel DPA flag and compliance obligations, which are independent base facts.
- **Enforcement tiers:** Version X's differentiated consequences are kept over Version Y's flat structure. Data and tool violations (items 1–2) trigger immediate action; process violations (items 3–5) trigger mandatory remediation first, then disciplinary review, with escalation for repeats. This distinction is operationally meaningful and more defensible in an employment context. Version Y's "condition of employment" is replaced with Version X's reference to the existing HR acknowledgment process, which is enforceable without new tooling.