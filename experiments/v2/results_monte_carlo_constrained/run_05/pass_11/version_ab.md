# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables.
2. GitHub Copilot Business is the sole approved AI tool, with 80 seats allocated to engineers and managed by the company.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) may be used for code completion, test generation, and documentation.
2. GitHub Copilot Business prompts and accepted suggestions must not include customer PII, financial data, or database schemas.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer PII, financial data, or database schemas into any AI service is prohibited. *(Motivating facts: Incident #1 schema exposure; outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses for any work-related task is prohibited, including AI tools used for sales email drafting. *(Motivating facts: Incident #2 verbatim copyrighted copy in AI-drafted sales email; outside counsel DPA violation flag; pending FedRAMP authorization.)*
3. **No AI-generated code submitted without license review.** The employee submitting a pull request must confirm no third-party license headers or GPL markers are present; pull request reviewers must reject any submission lacking that confirmation. *(Motivating facts: Incident #3 GPL header commit; outside counsel copyright non-ownership flag.)*
4. **No GitHub Copilot output distributed externally without Legal sign-off.** Any externally distributed content that includes GitHub Copilot output requires Legal review before distribution. *(Motivating fact: Outside counsel copyright non-ownership flag for AI-generated code.)*
5. **Slack AI features must remain disabled.** No employee may enable or request enablement of Slack AI features. *(Motivating fact: Slack AI features are currently disabled by company configuration; this policy codifies that state as a requirement.)*

---

## Enforcement

1. Violations of Prohibited Uses items 1–2 result in immediate disciplinary action for the responsible employee, up to and including termination.
2. Violations of Prohibited Uses items 3–5 are subject to disciplinary action for the responsible employee, up to and including termination.
3. Pull request reviewers who approve merges containing unlicensed AI-generated code without confirming compliance share accountability for the violation and are subject to disciplinary action.
4. Compliance with this policy is a condition of employment.

---

**Synthesis rationale:** Scope drops Version Y's redundant item 3 (Version X's fix). Permitted Uses adopts Version Y's two-item split for clarity. Prohibited Uses uses Version X's Slack citation (grounded in company configuration, not an inference about DPA scope) and Version X's Prohibition 4 citation (outside counsel copyright flag only, not Incident #2, which involved an unapproved tool already covered by Prohibition 2). Enforcement drops Version Y's "security incidents" classification (undefined term) in favor of Version X's direct disciplinary language, while retaining Version Y's cleaner two-tier structure separating data/tool violations from process violations.