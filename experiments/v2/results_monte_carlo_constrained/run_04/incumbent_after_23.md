# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy applies to all 200 employees and interns.
2. This policy governs all use of AI-assisted tools for any work-related task.
3. This policy operates within and supplements the company's SOC2 Type II, GDPR, and pending FedRAMP compliance obligations.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, capped at 80 seats provisioned and tracked by IT through existing access controls tied to the company's Copilot Business license.
2. Engineers may use GitHub Copilot Business only in work that does not involve customer PII, financial data, or database schemas. The PR author must confirm this in the PR description; the reviewer must confirm that declaration is present before approving. Approving without that confirmation is a policy violation by the reviewer, subject to Enforcement item 5.
3. All AI-generated code must pass PR review. The author must declare in the PR description that no third-party license notices are present; the reviewer must confirm that declaration before approving. Approving without that confirmation is a policy violation by the reviewer, subject to Enforcement item 5.
4. Additional AI tools may be approved upon written sign-off by Legal and Security, documented in writing and tracked by IT, within the $50K annual AI tooling budget.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Incident #1; DPA violation risk per outside counsel; GDPR obligations; SOC2 Type II certification; pending FedRAMP authorization.)*
2. **No verbatim third-party copyrighted content.** Employees must not submit, send, or publish AI-generated content that contains verbatim third-party copyrighted text. *(Incident #2: a sales rep submitted AI-generated text containing a competitor's copyrighted marketing copy verbatim.)*
3. **No unapproved AI writing tools.** Sales and non-engineering employees must not use any AI writing tool not approved under Permitted Use #4. *(Incident #2; informal survey finding that 45% of sales are already using AI for email drafting with no approved tool in place.)*
4. **No committing AI-generated code containing third-party license notices.** *(Incident #3: an intern committed AI-generated code carrying a GPL license header from training data; outside counsel flagged that AI-generated code may not be copyrightable, making unresolved third-party license notices a direct IP liability.)*
5. **No use of Slack AI features.** Employees must not enable or use any AI feature within the company Slack instance. *(Inputting company data into Slack AI constitutes use of a third-party AI service, which risks violating existing DPA terms per outside counsel; SOC2 Type II certification; pending FedRAMP authorization.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing access controls, within the 80-seat hard cap on the company's Copilot Business license.
2. The PR approval gate in Permitted Uses #2 and #3 is enforced through the existing PR review process. A reviewer who approves without the required author declarations has committed a policy violation and is subject to item 5 of this section.
3. IT must disable any Slack AI feature found re-enabled and report the incident to Legal immediately upon discovery.
4. Suspected violations must be reported to Legal and Security via the existing incident reporting channel immediately upon discovery.
5. Confirmed violations result in suspension of AI tool access by IT, pending a written reinstatement decision by the employee's manager and HR through the standard HR process.