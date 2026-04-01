# AI Tool Usage Policy

**Owner:** CTO & General Counsel | **Review Cycle:** Quarterly

---

## Scope

1. This policy applies to all 200 employees, contractors, and interns across engineering, sales, and all other functions, effective immediately upon issuance.
2. This policy governs any use of AI tools for work-related tasks, including coding, writing, data analysis, and customer communications.
3. Informal survey data confirms 73% of engineers and 45% of sales staff are already using AI tools without an official policy; this policy supersedes all prior informal practices.
4. This policy is issued under SOC2 Type II, GDPR, and pending FedRAMP obligations that govern how customer PII and financial data are handled.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI tool for engineers. Use is limited to the 80 licensed seats currently provisioned; Engineering leadership manages seat allocation.
2. Engineers may use GitHub Copilot for code suggestions, boilerplate generation, and test writing on codebases that contain no customer PII or financial data.
3. Requests for additional AI tools are submitted to the CTO and Legal for approval. All approvals are governed by the $50,000 annual AI tooling budget.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, database schemas, or any customer-identifiable information into any non-approved AI service is prohibited. *(Motivating facts: Incident 1 — engineer pasted customer database schema into ChatGPT; outside counsel finding that this likely violates existing DPA terms; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects without the sender's manager reviewing and approving it for accuracy, originality, and legal compliance. *(Motivating fact: Incident 2 — sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code committed without license review.** Code produced by AI tools may not be committed without the pull request reviewer confirming in writing that no third-party license headers or GPL-encumbered content are present. *(Motivating facts: Incident 3 — intern committed code with a GPL license header sourced from AI training data; outside counsel finding that AI-generated code may not be copyrightable.)*
4. **Slack AI features must remain disabled.** Enabling or circumventing the disabled AI features in company Slack is prohibited. *(Motivating fact: Company Slack is a provisioned tool with AI features currently disabled as a configured control.)*
5. **No unapproved AI tools on company systems.** Accessing or installing non-approved AI services via company devices, accounts, or networks is prohibited. *(Motivating facts: GitHub Copilot Business is the only approved tool; outside counsel finding that inputting company or customer data into unapproved third-party services likely violates DPA terms.)*

---

## Enforcement

1. Violations involving customer data exposure are reported and handled as security incidents under the existing SOC2 incident response procedure, which triggers mandatory breach assessment. All other violations are reported to the employee's direct manager, the CTO, and Legal upon discovery.
2. The pull request reviewer sign-off required by GitHub's existing review gate is the control that enforces the license-review requirement in Prohibition 3; no merge proceeds without it. No new tooling is required.
3. First violations result in mandatory remediation training and a written warning. Repeated violations result in disciplinary action up to and including termination.
4. Managers are accountable for their team's compliance. Quarterly access reviews audit GitHub Copilot seat usage against this policy.