# AI Tool Usage Policy
**Effective Date:** [Date] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools—including code assistants, writing tools, and generative AI services—by all 200 employees in company-owned and personal workflows connected to company data or deliverables.
2. This policy supersedes all informal practices. Prior use without policy coverage does not establish precedent.
3. Compliance with this policy is a condition of employment and contractor engagement.

---

## Permitted Uses

1. **GitHub Copilot Business** (80 licensed seats) is the sole approved AI coding assistant. Engineers must use only licensed seats; seat assignments are managed by Engineering Ops.
2. Copilot may be used for code completion, test generation, and documentation on internal or proprietary codebases containing no customer PII or financial data.
3. AI-drafted sales and customer communications are permitted only when the final text is reviewed, edited, and sent by the authoring employee. AI attribution is not required externally.
4. Employees may submit requests for additional AI tools against the $50K annual tooling budget via Engineering or Department Heads. Tools require Legal sign-off before use.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer PII, financial data, or database schemas into any AI service—including ChatGPT or any non-approved tool—is prohibited. *(Motivating facts: Incident #1 schema exposure; outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unapproved external AI services.** Using AI tools not authorized under Section 2 for any work-related task is prohibited. *(Motivating facts: DPA terms flagged by outside counsel; FedRAMP authorization risk.)*
3. **No unreviewed AI-generated code committed to production.** All AI-generated code requires human review confirming the absence of third-party license headers, GPL markers, or verbatim copied text before merge. *(Motivating facts: Incident #3 GPL header commit; outside counsel copyright non-ownership flag.)*
4. **No AI-generated content published externally without plagiarism/IP review.** Sales or marketing content must be checked against source material before external distribution. *(Motivating fact: Incident #2 verbatim competitor copyrighted copy.)*
5. **Slack AI features remain disabled.** No employee may request or configure re-enablement without CISO and Legal approval. *(Motivating fact: Slack AI features currently disabled as a deliberate control.)*

---

## Enforcement

1. Violations of Prohibited Use items 1–2 are reportable security incidents. Employees must self-report to Security within 24 hours of discovery; managers must escalate to CISO within 48 hours.
2. Engineering Leads conduct AI-usage spot audits during existing monthly code review cycles. No new tooling is required.
3. Pull request templates are updated immediately to include a mandatory checkbox: *"No AI-generated code present, OR AI-generated code reviewed for license markers and IP conflicts."*
4. First violations result in mandatory retraining and documented written warning. Repeat or willful violations proceed under the standard disciplinary process, up to and including termination.
5. Legal reviews this policy at each SOC2 audit cycle and prior to FedRAMP authorization submission.