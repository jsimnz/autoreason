# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Audience:** All Employees

---

## Scope

1. This policy applies to all 200 employees, contractors, and interns across engineering, sales, and all other functions.
2. This policy governs any use of AI tools—including code assistants, text generators, and chat interfaces—for work-related tasks.
3. This policy supersedes all informal practices currently in use.

---

## Permitted Uses

1. **Engineers:** GitHub Copilot Business (licensed, 80 seats) is the sole approved AI coding assistant. Seat requests go to Engineering Leads; unused seats are reallocated quarterly.
2. **Engineers:** AI-assisted code is permitted only when the committing engineer reviews, understands, and accepts ownership of every line before commit.
3. **Sales:** AI drafting tools are permitted exclusively for internal draft generation using only non-confidential, non-customer data. All outbound content requires human review before sending.
4. **All employees:** AI tool use is permitted only within the $50K annual tooling budget; purchases require Finance pre-approval.
5. **All employees:** GitHub Copilot Business is approved because it operates under an enterprise data agreement. No other external AI service is approved for work tasks.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data—including database schemas, records, or identifiers—into any third-party AI service is prohibited. *(Motivating facts: Engineer pasted customer database schema into ChatGPT; outside counsel confirmed this likely violates existing DPA terms; SOC2 Type II and GDPR obligations apply to customer PII and financial data.)*
2. **No unreviewed AI-generated content in outbound communications.** Publishing or sending AI-generated text without verifying it is original is prohibited. *(Motivating fact: Sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim.)*
3. **No AI-generated code committed without license header review.** Engineers must confirm no open-source license artifacts (e.g., GPL headers) are present before committing AI-generated code. *(Motivating facts: Intern committed code with a GPL header from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
4. **No use of unapproved AI tools for any work purpose.** Using consumer AI products (e.g., ChatGPT free tier, personal Copilot accounts) for work tasks is prohibited. *(Motivating fact: 73% of engineers and 45% of sales already using unapproved tools with no data controls.)*
5. **No enabling of AI features in company Slack.** Slack AI features remain disabled; employees do not enable them. *(Motivating fact: Company Slack has AI features disabled; FedRAMP authorization is pending Q3.)*

---

## Enforcement

1. Engineering Leads conduct AI tool compliance checks during existing quarterly code reviews; violations trigger a written warning on first offense.
2. A second violation results in revocation of GitHub Copilot seat access, enforced by the Engineering Lead via GitHub admin controls.
3. Violations involving customer data (Prohibited Use #1) are escalated immediately to Legal and the DPO and treated as a potential data incident under the existing SOC2 incident response process.
4. Sales Managers verify AI disclosure in existing deal review meetings; undisclosed AI use in customer-facing content is subject to HR disciplinary review.
5. All three incidents from the prior quarter are retroactively classified under this policy and documented in employee records accordingly.