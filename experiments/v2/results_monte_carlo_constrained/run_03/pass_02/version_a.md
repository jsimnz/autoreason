I'll address each problem systematically before presenting the revised document.

**Changes made and problems fixed:**

- **Problem 1 (word count):** Tightened prose throughout all sections; removed the metadata header entirely (also fixes Problem 9).
- **Problem 2 (Prohibition 4 missing citation):** Added motivating fact citation referencing the base fact that Slack AI features are currently disabled.
- **Problem 3 (Prohibition 5 missing citation):** Added motivating fact citation referencing the approved tools list and outside counsel's DPA finding.
- **Problem 4 (no approved sales drafting tool):** Removed the reference to "AI-assisted drafting tools integrated natively into approved platforms." Sales has no approved AI tool; the permitted use now reflects that accurately.
- **Problem 5 (survey figures unused):** Added a Scope item incorporating the 73%/45% usage figures as the factual basis for the policy.
- **Problem 6 (GitHub gates overclaimed):** Replaced the assertion that GitHub gates automatically enforce license review with a statement that the existing pull request reviewer sign-off requirement (an existing access control) is the enforcement mechanism, with the license check as a named reviewer obligation.
- **Problem 7 (unenforceable review requirement):** Specified that the sender's manager is the named approver for AI-generated customer-facing content.
- **Problem 8 (24-hour reporting has no mechanism):** Replaced with a reference to the existing SOC2 incident response procedure as the reporting mechanism, removing the invented 24-hour pipeline.
- **Problem 9 (metadata header):** Removed entirely.

---

# AI Tool Usage Policy

## Scope

1. This policy applies to all 200 employees, contractors, and interns across all functions, effective immediately upon issuance.
2. This policy governs any use of AI tools for work-related tasks, including coding, writing, data analysis, and customer communications.
3. Informal survey data confirms 73% of engineers and 45% of sales staff are already using AI tools without an official policy; this policy supersedes all prior informal practices.
4. This policy is issued under SOC2 Type II, GDPR, and pending FedRAMP obligations that govern how customer PII and financial data are handled.

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI tool for engineers. Use is limited to the 80 licensed seats provisioned; Engineering leadership manages seat allocation.
2. Engineers may use GitHub Copilot for code suggestions, boilerplate generation, and test writing on codebases that contain no customer PII or financial data.
3. Requests for additional AI tools are submitted to the CTO and Legal for approval. All approvals are governed by the $50,000 annual AI tooling budget.

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, database schemas, or any customer-identifiable information into any non-approved AI service is prohibited. *(Motivating facts: Incident 1 — engineer pasted customer database schema into ChatGPT; outside counsel finding that this likely violates existing DPA terms; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects without the sender's manager reviewing and approving it for accuracy, originality, and legal compliance. *(Motivating fact: Incident 2 — sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code committed without license review.** Code produced by AI tools may not be committed without the pull request reviewer confirming in writing that no third-party license headers or GPL-encumbered content are present. *(Motivating facts: Incident 3 — intern committed code with a GPL license header sourced from AI training data; outside counsel finding that AI-generated code may not be copyrightable.)*
4. **Slack AI features must remain disabled.** Enabling or circumventing the disabled AI features in company Slack is prohibited. *(Motivating fact: Company Slack is a provisioned tool with AI features currently disabled as a configured control.)*
5. **No unapproved AI tools on company systems.** Accessing or installing non-approved AI services via company devices, accounts, or networks is prohibited. *(Motivating facts: GitHub Copilot Business is the only approved tool; outside counsel finding that inputting company or customer data into unapproved third-party services likely violates DPA terms.)*

## Enforcement

1. Violations involving customer data exposure are reported and handled as security incidents under the existing SOC2 incident response procedure, which triggers mandatory breach assessment.
2. The pull request reviewer sign-off required by GitHub's existing review gate is the control that enforces the license-review requirement in Prohibition 3; no merge proceeds without it.
3. First violations result in mandatory remediation training and a written warning. Repeated violations result in disciplinary action up to and including termination.
4. Managers are accountable for their team's compliance. Quarterly access reviews audit GitHub Copilot seat usage against this policy.