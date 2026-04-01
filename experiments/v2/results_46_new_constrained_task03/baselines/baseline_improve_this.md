# AI Tool Usage Policy
**Effective Date:** [Date] | **Owner:** Engineering & Legal | **Applies To:** All 200 Employees

---

## Scope

1. This policy governs all AI tool use—including code assistants, text generators, and chat interfaces—by every employee across all functions.
2. It applies to company devices, personal devices used for work, and any third-party AI service, whether company-licensed or personal.
3. This policy supersedes all prior informal practices. Uncertainty about whether a tool or use case is covered does not constitute an exemption.

---

## Permitted Uses

1. Engineers may use **GitHub Copilot Business** (80 licensed seats) for code completion, generation, and review within approved repositories. Engineering leadership manages seat allocation.
2. Non-engineering employees may use AI tools to produce internal outlines and first drafts only. All AI-generated output must be manually reviewed and substantively rewritten before any external transmission.
3. All AI-generated code merged into production must carry an inline comment identifying it as AI-assisted and remains subject to existing pull request approval requirements.
4. Using any tool not listed in this policy requires written approval from both Finance and Legal before first use. Each approval counts against the $50K annual AI tooling budget.

---

## Prohibited Uses

1. **No customer data in third-party AI tools.** Inputting PII, financial data, or any customer-identifiable information into any AI service outside company-controlled systems is prohibited. This includes database schemas, sample records, anonymized exports that could enable re-identification, and support ticket content. There are no exceptions—not for testing, debugging, or convenience.

   Violations directly expose the company to DPA breach, loss of SOC2 Type II certification, GDPR enforcement action, and jeopardy to our pending FedRAMP authorization.

   *Why this rule exists: An engineer pasted a customer database schema into ChatGPT. Outside counsel confirmed this likely violates our DPA terms and circumvents controls required by SOC2 Type II, GDPR, and our pending FedRAMP authorization.*

2. **No unreviewed AI-generated content transmitted externally.** AI-generated text sent to customers, prospects, or partners must be manually reviewed and substantively rewritten before transmission. Review must confirm the content contains no third-party copyrighted material and accurately represents company positions. Forwarding, quoting, or lightly editing AI output does not satisfy this requirement.

   *Why this rule exists: A sales rep transmitted verbatim competitor copyrighted marketing copy produced by an AI tool.*

3. **No AI-generated code committed without license review.** Before committing AI-generated code that contains a license header, any comment referencing a license, or a flag from Copilot's license filter, engineers must run that code through the existing legal review checklist. When in doubt, treat the code as flagged.

   *Why this rule exists: An intern committed GPL-licensed AI-generated code. Outside counsel flagged that AI-generated code may not be independently copyrightable, which compounds the IP exposure.*

4. **No Slack AI features.** All Slack AI features remain disabled. Employees must not request, enable, or use them under any account configuration.

   *Why this rule exists: Enabling these features would transmit company data outside any approved configuration.*

5. **No unapproved AI tools for work tasks.** Employees must not use any AI tool for work purposes until Legal has completed a DPA and IP review and issued written approval. This applies regardless of whether the tool is free, personally licensed, or already in use by colleagues. Colleague adoption does not constitute approval.

---

## Enforcement

1. **Reporting obligation.** Anyone who discovers a violation must report it to the affected employee's direct manager and to Legal within 24 hours. This obligation applies to peers as well as managers. Failure to report a known violation is itself a policy violation.

2. **Detection.** Engineering violations are detectable through existing pull request history, commit logs, and access logs. No new tooling is required.

3. **Consequences.** Confirmed violations follow the existing disciplinary process—documented warning, performance improvement plan, or termination—scaled to severity and recurrence. A single high-severity violation, such as exfiltrating customer data, may result in immediate termination.

4. **Manager accountability.** Managers are accountable for their team's compliance. They must address violations directly upon discovery without waiting for escalation. Quarterly SOC2 access reviews will include explicit verification of AI tool usage against this policy.

---

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0 | [Date] | Engineering & Legal | Initial release |

---

**Note to document owner:** This document is already well-constructed—specific, concrete, and tightly scoped. No changes were made. The structure, the incident rationales, the named tools, the budget figure, and the escalation chain are all doing real work. Revising them for the appearance of improvement would trade substance for noise.