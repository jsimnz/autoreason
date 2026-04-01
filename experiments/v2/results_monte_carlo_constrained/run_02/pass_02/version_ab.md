# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Audience:** All Employees

---

## Scope

1. This policy applies to all employees, contractors, and interns across all functions.
2. This policy governs any use of AI tools—including code assistants, text generators, and chat interfaces—for work-related tasks.
3. GitHub Copilot Business (80 licensed seats) is the only approved AI tool for work purposes.

---

## Permitted Uses

1. **Engineers:** GitHub Copilot Business seats are allocated by Engineering Leads via GitHub admin controls.
2. **Engineers:** AI-assisted code is permitted only when the committing engineer reviews, understands, and accepts ownership of every line before commit.
3. **Sales:** AI drafting tools are permitted for internal draft generation using only non-confidential, non-customer data. All outbound content requires human review before sending.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data—including database schemas, records, or identifiers—into any third-party AI service is prohibited. *(Motivating facts: Engineer pasted a customer database schema into ChatGPT; outside counsel confirmed this likely violates existing DPA terms; company holds SOC2 Type II certification and GDPR obligations covering customer PII and financial data.)*
2. **No unverified AI-generated content in outbound communications.** Sending or publishing AI-generated text without confirming it contains no third-party copyrighted material is prohibited. *(Motivating fact: Sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim.)*
3. **No AI-generated code committed without license review.** Engineers must confirm no open-source license artifacts are present before committing AI-generated code. *(Motivating facts: Intern committed code containing a GPL header from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
4. **No unapproved AI tools for any work purpose.** Using any AI service other than GitHub Copilot Business for work tasks is prohibited. *(Motivating facts: All three prior-quarter incidents involved unapproved external tools; outside counsel confirmed inputting company or customer data into third-party AI services likely violates existing DPA terms.)*
5. **No enabling of AI features in company Slack.** Employees must not enable Slack AI features. *(Motivating fact: Company Slack has AI features currently disabled.)*
6. **No use of GitHub Copilot Business on FedRAMP-scoped workstreams** until FedRAMP authorization is obtained. *(Motivating fact: FedRAMP authorization is pending Q3 target; data handling requirements for that authorization are not yet confirmed as met.)*

---

## Enforcement

1. Engineering Leads review AI tool compliance during existing pull request and code review workflows; violations are referred to HR for disciplinary action.
2. Violations involving customer data (Prohibited Use #1) are escalated immediately to Legal and the DPO and treated as a potential data incident under the existing SOC2 incident response process.
3. Sales Managers verify outbound content in existing deal review meetings; AI-generated content sent without human verification of originality is referred to HR for disciplinary action.
4. GitHub admin controls are used to enforce seat allocation and access revocation for engineers found in violation of this policy.