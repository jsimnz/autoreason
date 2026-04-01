# AI Tool Usage Policy
**Effective Date:** [Date] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables.
2. An informal survey found 73% of engineers and 45% of sales staff already use AI tools; this policy applies immediately to all current and future use.
3. GitHub Copilot Business is licensed for 80 of 120 engineers; the company manages seat allocation and prioritization for engineers without seats.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) is the sole approved AI coding assistant. It may be used for code completion, test generation, and documentation on codebases containing no customer PII or financial data.
2. AI writing tools may be used for internal drafting only. Any AI-assisted content intended for external distribution must be reviewed, edited, and verified by the authoring employee before sending.
3. Additional AI tools require approval before use and are funded from the $50K annual tooling budget.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer PII, financial data, or database schemas into any AI service is prohibited. *(Motivating facts: Incident #1 schema exposure; outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unapproved external AI services.** Using AI tools not listed in Permitted Uses for any work-related task is prohibited. *(Motivating facts: Outside counsel DPA violation flag; pending FedRAMP authorization.)*
3. **No AI-generated code committed without license review.** All AI-generated code requires pull request reviewer confirmation of no third-party license headers or GPL markers before merge. *(Motivating facts: Incident #3 GPL header commit; outside counsel copyright non-ownership flag.)*
4. **No AI-generated content distributed externally without IP review.** AI-assisted sales and marketing content must be verified against source material by the authoring employee before external distribution. *(Motivating fact: Incident #2 verbatim competitor copyrighted copy.)*
5. **Slack AI features must not be enabled.** No employee may configure or request re-enablement of Slack AI features. *(Motivating fact: Current company configuration disables these features.)*

---

## Enforcement

1. Violations of Prohibited Use items 1–2 are reportable security incidents. Employees must self-report to Security promptly; managers must escalate to Security. Failure to self-report is itself a violation.
2. The authoring employee is responsible for confirming that AI-assisted outbound communications have been reviewed and edited before external distribution, as required by Permitted Uses item 2.
3. The pull request reviewer confirms AI-generated code is free of license markers before approving merge, as required by Prohibited Uses item 3.
4. Compliance with this policy is a condition of employment. Violations are subject to disciplinary action up to and including termination.

---

**Synthesis rationale:** Scope and Permitted Uses adopt Version Y's cleaner formulations, replacing invented roles ("Engineering Ops") with "the company" and removing the invented Legal submission channel. Prohibited Uses retains Version X's Slack prohibition (item 5) — the current disabled configuration is a base fact, and permitting re-enablement without restriction would be inconsistent with it, making the prohibition derivable. Prohibited Uses items 1–4 use Version Y's tighter language and its superior framing of item 4, which correctly places the verification obligation on the authoring employee. Enforcement combines both versions: Version X's manager escalation duty in item 1 (which adds an enforceable check without inventing new tooling or roles) alongside Version Y's cleaner role assignments in items 2 and 3, which replace invented titles with roles directly derivable from existing processes.