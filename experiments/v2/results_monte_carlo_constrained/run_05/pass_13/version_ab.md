# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables.
2. GitHub Copilot Business is the sole currently approved AI tool, with 80 seats allocated to engineers. A $50K annual budget is allocated for additional AI tooling approved per Enforcement item 4.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) may be used for code completion, test generation, and documentation on non-customer data.
2. Sales employees currently using unapproved AI tools for email drafting have a 30-day grace period from the Effective Date to transition to approved tools. During this period, Prohibited Uses item 2 is not enforced against sales employees for email drafting only; all other prohibitions apply in full.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer PII, financial data, or database schemas into any AI service is prohibited. *(Motivating facts: Incident #1 schema exposure; outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses for any work-related task is prohibited. *(Motivating facts: Incident #2 verbatim copyrighted copy in AI-drafted sales email; outside counsel DPA violation flag; pending FedRAMP authorization.)*
3. **No AI-generated code submitted without license review.** The submitting employee must confirm no third-party license headers or GPL markers are present; pull request reviewers must reject any submission lacking that confirmation. *(Motivating facts: Incident #3 GPL header commit; outside counsel copyright non-ownership flag.)*
4. **No GitHub Copilot output distributed externally without Legal sign-off.** Any externally distributed content that includes GitHub Copilot output requires Legal review before distribution. *(Motivating fact: Outside counsel copyright non-ownership flag for AI-generated code.)*

---

## Enforcement

1. Violations of Prohibited Uses items 1–2 result in immediate disciplinary action, up to and including termination.
2. Violations of Prohibited Uses items 3–4 require mandatory remediation — the affected code or content is reverted or withheld — followed by disciplinary review. Repeated violations result in escalating discipline up to and including termination.
3. Pull request reviewers who approve merges containing unlicensed AI-generated code without confirming compliance share accountability and are subject to the same disciplinary review as the submitting employee.
4. Requests to approve new AI tools are submitted to Legal and Security in writing. Approved tools are added to Permitted Uses by written amendment signed by the CEO. No tool is used before that amendment is signed.
5. All employees acknowledge this policy annually via the existing annual policy acknowledgment process administered by HR.

---

**Synthesis rationale by decision point:**

- **Scope item 2:** Version Y's formulation is cleaner; the cross-reference to Enforcement item 4 is a navigational aid, not a circular dependency.
- **Permitted Uses item 2 (grace period vs. request path):** Version Y's 30-day grace period is the stronger solution. Version X routes sales employees through an approval process that has no guaranteed outcome or timeline, creating a foreseeable mass-violation scenario given the 45% current-usage base fact. Version Y's grace period acknowledges the existing behavior, sets a defined deadline, and preserves full enforcement of all other prohibitions during the transition.
- **Slack prohibition (Version X item 5):** Version Y's removal is correct. The base facts state Slack AI features are already disabled; no base fact establishes that employees have attempted or are likely to attempt enabling them. Version X's prohibition is not derivable from the base facts and was excluded.
- **Enforcement differentiation:** Both versions agree on the two-tier structure. Version Y's language is tighter and adopted without substantive change.
- **Enforcement item 5 (annual acknowledgment):** Version X introduced the HR acknowledgment process as a fix for the unanchored "condition of employment" language. Version Y retained it. Both agree; retained.