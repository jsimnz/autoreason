# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Audience:** All Employees

---

## Scope

1. This policy applies to all employees, contractors, and interns across all functions.
2. This policy governs any use of AI tools—including code assistants, text generators, and chat interfaces—for work-related tasks.
3. GitHub Copilot Business (80 licensed seats) is the only approved AI tool for work purposes; all other AI services are unapproved.

*Fixes #9: Approved tool designation moves to Scope, eliminating the redundancy between Permitted Use #5 and Prohibited Use #4.*

---

## Permitted Uses

1. **Engineers:** GitHub Copilot Business seats are allocated by Engineering Leads; unused seats are reallocated quarterly via GitHub admin controls.
2. **Engineers:** AI-assisted code is permitted only when the committing engineer reviews, understands, and accepts ownership of every line before commit.
3. **Sales:** AI drafting tools are permitted for internal draft generation using only non-confidential, non-customer data. All outbound content requires human review before sending.
4. **All employees:** New AI tool purchases require Finance pre-approval against the designated $50K annual AI tooling budget.
5. **All employees:** GitHub Copilot Business operates under an enterprise data agreement. Confirm with Legal before use on any work stream subject to FedRAMP requirements, pending Q3 authorization.

*Fixes #4: Budget item now addresses Finance pre-approval for purchases—a rule employees can follow—rather than tracking headroom. Fixes #6: FedRAMP implications are addressed in Permitted Uses with a concrete directive.*

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data—including database schemas, records, or identifiers—into any third-party AI service is prohibited. *(Motivating facts: Engineer pasted a customer database schema into ChatGPT; outside counsel confirmed this likely violates existing DPA terms; company holds SOC2 Type II certification and GDPR obligations covering customer PII and financial data.)*
2. **No unreviewed AI-generated content in outbound communications.** Sending or publishing AI-generated text without verifying it is original is prohibited. *(Motivating fact: Sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim.)*
3. **No AI-generated code committed without license review.** Engineers must confirm no open-source license artifacts (e.g., GPL headers) are present before committing AI-generated code. *(Motivating facts: Intern committed code containing a GPL header from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
4. **No use of unapproved AI tools for any work purpose.** Using consumer AI products (e.g., free-tier ChatGPT, personal Copilot accounts) for work tasks is prohibited. *(Motivating fact: Informal survey found 73% of engineers and 45% of sales already using AI tools under no official policy.)*
5. **No enabling of AI features in company Slack.** Slack AI features are disabled company-wide; employees must not enable them. *(Motivating facts: Company Slack has AI features currently disabled; FedRAMP authorization is pending Q3.)*

*Fixes #5: Motivating fact for Prohibited Use #4 now cites the survey finding as stated, without adding the inference "no data controls." Fixes #2: "must not enable" replaces the ambiguous "do not enable."*

---

## Enforcement

1. Engineering Leads review AI tool compliance during existing pull request and code review workflows; violations result in a written warning on first offense.
2. A second violation results in revocation of GitHub Copilot seat access, enforced by the Engineering Lead via GitHub admin controls.
3. Violations involving customer data (Prohibited Use #1) are escalated immediately to Legal and the DPO and treated as a potential data incident under the existing SOC2 incident response process.
4. Sales Managers verify AI disclosure during existing deal review meetings; undisclosed AI use in customer-facing content is subject to HR disciplinary review.

*Fixes #3: Enforcement item 5 (retroactive reclassification of prior incidents) is removed as it required a new administrative process. Fixes #7: "quarterly code reviews" replaced with "pull request and code review workflows," which are standard existing engineering processes derivable from a 120-person engineering org without inventing new mechanisms.*

---

*Scope item 3 replaces the removed Permitted Use #5 and the boilerplate "supersedes" item, consolidating approved-tool designation into a single location. Fixes #8: The non-operative "supersedes" item is removed. Fixes #9: Redundancy between former Permitted Use #5 and Prohibited Use #4 is eliminated.*