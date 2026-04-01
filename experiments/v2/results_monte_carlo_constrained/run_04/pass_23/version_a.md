# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy applies to all 200 employees and interns.
2. This policy governs all use of AI-assisted tools for any work-related task.
3. This policy operates within and supplements the company's existing SOC2 Type II, GDPR, and pending FedRAMP compliance obligations.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, capped at 80 seats provisioned and tracked through the existing identity management system.
2. Engineers may use GitHub Copilot Business only in work that does not involve customer PII, financial data, or database schemas. The PR author must confirm this in the PR description; the reviewer must verify before approving.
3. All AI-generated code must pass PR review. The author must declare no third-party license notices are present; the reviewer must confirm that declaration before approving.
4. Additional AI tools may be approved upon written sign-off by Legal and Security, documented in the existing identity management system, within the $50K annual AI tooling budget.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Incident #1; DPA violation risk per outside counsel; GDPR obligations; SOC2 Type II; pending FedRAMP.)*
2. **No verbatim third-party copyrighted content.** Employees must not submit, send, or publish AI-generated content that contains verbatim third-party copyrighted text. *(Incident #2.)*
3. **No unapproved AI writing tools.** Sales and non-engineering employees must not use any AI writing tool not approved under Permitted Use #4. *(Incident #2; 45% of sales using AI for email drafting.)*
4. **No committing AI-generated code with third-party license notices.** *(Incident #3; outside counsel flagged AI-generated code may not be copyrightable.)*
5. **No delivering AI-generated code to customers as proprietary work product.** *(Outside counsel flagged AI-generated code may not be copyrightable.)*
6. **No use of Slack AI features.** Employees must not enable or use any AI feature within the company Slack instance. *(Inputting company data into Slack AI constitutes use of a third-party AI service; DPA violation risk per outside counsel; SOC2 Type II; pending FedRAMP.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through the existing identity management system within the 80-seat hard cap.
2. The PR approval gate requires reviewer confirmation of the author's data and license declarations. Approving without those confirmations is a policy violation by the reviewer.
3. IT must disable any Slack AI feature found re-enabled and report to Legal within 24 hours of discovery.
4. Suspected violations must be reported to Legal and Security via the existing incident reporting channel within 24 hours of discovery.
5. For violations involving AI-generated content distributed without tool access to revoke (including copyright incidents under Prohibited Use #2), the employee's manager and Legal must conduct a written review and produce a documented remediation plan within five business days. Termination decisions follow standard HR and Legal process.
6. All other confirmed violations result in immediate suspension of AI tool access by IT, pending a written reinstatement decision by the employee's manager and HR.

---

**Synthesis rationale by decision:**

- **Scope item 3:** Retained from Version X. Version Y omitted this item entirely; the explicit compliance-obligations anchor is stronger than silence and is fully derivable from base facts.
- **Permitted Use #1 / identity management system:** Version X's "existing identity management system" adopted over Version Y's "IT provisioning log." The former is derivable from SOC2 certification and the existing Copilot license; the latter implies new infrastructure not established in base facts.
- **Prohibited Use #3 motivating citation:** Version X's citation ("45% of sales using AI for email drafting") adopted over Version Y's ("45% of sales using unapproved tools with no safeguard in place"). Version Y's phrasing adds an editorial characterization not present in the base fact.
- **Prohibited Use #6 motivating citation:** Version X's full citation adopted over Version Y's. Version Y cited only the company configuration fact, which is circular — it states the current state, not the reason the state must be maintained. Version X correctly grounds the prohibition in DPA risk, SOC2, and FedRAMP, all of which are base facts.
- **Enforcement item 5:** Version X's formulation adopted over Version Y's. Version Y required a "remediation or termination decision" within five business days, imposing a fixed deadline on a termination decision — a constraint that conflicts with standard HR and Legal process and is not supported by any base fact. Version X separates the remediation-plan deadline from the termination decision, which follows existing process.