I'll address each problem in turn, then present the revised document.

**Changes made and why:**

- **Problem 1 (word count):** Compressed all sections by eliminating redundant phrasing, collapsing motivating-fact citations to inline references, and tightening enforcement items.
- **Problem 3 (scope too narrow):** Scope item 2 now covers all AI-assisted tools for any work-related task, not just the three named categories.
- **Problem 4 (Prohibited Use #3 contradicts Permitted Use #4):** Prohibited Use #3 now bans unapproved AI writing tools for sales/non-engineering, preserving the approval pathway in Permitted Use #4.
- **Problem 5 (fabricated motivating fact in Prohibited Use #6):** Motivating fact rewritten to cite only the base fact: Slack AI features are currently disabled per company configuration.
- **Problem 6 (Permitted Use #2 requires new tooling):** Replaced the "IT repository access registry" with the existing PR review process and the existing data classification already required for SOC2/GDPR compliance, which are derivable from base facts.
- **Problem 7 (Enforcement item 3 assumes new process):** Removed the "monthly IT review cycle" language; replaced with a triggered check by IT whenever Slack is reconfigured, which requires no new process.
- **Problem 8 (Permitted Use #4 implies new infrastructure):** Tightened the item to reference only the documented sign-off step, which is a decision gate rather than a new system.
- **Problem 9 (no enforcement consequence for copyright violators without tool access):** Added an enforcement item specifically covering copyright/IP incidents where tool-access revocation is inapplicable, imposing a mandatory manager-and-Legal review instead.
- **Problem 2 (Prohibited Use #5 creates implicit permission pathway):** Removed the "without Legal review" carve-out; the prohibition now reflects the full strength of the motivating fact.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy applies to all 200 employees and interns.
2. This policy governs all use of AI-assisted tools for any work-related task.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, capped at 80 seats provisioned and tracked in the IT provisioning log.
2. Engineers may use GitHub Copilot Business only in work that does not involve customer PII, financial data, or database schemas. The PR author must confirm this in the PR description; the reviewer must verify before approving.
3. All AI-generated code must pass PR review. The author must declare no third-party license notices are present; the reviewer must confirm that declaration before approving.
4. Additional AI tools may be approved upon written sign-off by Legal and Security, documented in the IT provisioning log, within the $50K annual AI tooling budget.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Incidents #1; DPA violation risk per outside counsel; GDPR obligations; SOC2 Type II; pending FedRAMP.)*
2. **No verbatim third-party copyrighted content.** Employees must not submit, send, or publish AI-generated content that contains verbatim third-party copyrighted text. *(Incident #2.)*
3. **No unapproved AI writing tools.** Sales and non-engineering employees must not use any AI writing tool not approved under Permitted Use #4. *(Incident #2; 45% of sales using unapproved tools with no safeguard in place.)*
4. **No committing AI-generated code with third-party license notices.** *(Incident #3; outside counsel flagged AI-generated code may not be copyrightable.)*
5. **No delivering AI-generated code to customers as proprietary work product.** *(Outside counsel flagged AI-generated code may not be copyrightable.)*
6. **No use of Slack AI features.** Employees must not enable or use any AI feature within the company Slack instance. *(Slack AI features are currently disabled per company configuration.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management within the 80-seat hard cap.
2. The PR approval gate requires reviewer confirmation of the author's data and license declarations. Approving without those confirmations is a policy violation by the reviewer.
3. IT must disable any Slack AI feature found re-enabled and report to Legal within 24 hours of discovery.
4. Suspected violations must be reported to Legal and Security via the existing incident reporting channel within 24 hours of discovery.
5. For violations involving AI-generated content distributed without tool access to revoke (including copyright incidents under Prohibited Use #2), the employee's manager and Legal must conduct a written review within five business days and issue a documented remediation or termination decision.
6. All other confirmed violations result in immediate suspension of AI tool access by IT, pending a written reinstatement or termination decision by the employee's manager and HR.