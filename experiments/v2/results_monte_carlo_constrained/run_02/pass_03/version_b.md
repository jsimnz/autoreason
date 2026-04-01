I'll address each problem, then present the revised document.

**Changes made and problems each fixes:**

1. **Removed entire preamble/revision log** → fixes Problem #1 (inappropriate content) and Problem #2 (word count violation)
2. **Changed "Owner: Legal & Engineering" to "[OWNER]"** → fixes Problem #8 (invented content)
3. **Removed "DPO" from Enforcement #2; replaced with "Legal"** → fixes Problem #9 (DPO role not in base facts)
4. **Removed Incident #3 from Prohibited Use #4 motivating facts** → fixes Problem #3 (Incident #3 involved the approved tool, not an unapproved external tool)
5. **Rewrote Prohibited Use #5 motivating fact** to cite DPA violation risk and SOC2/GDPR obligations as the reason Slack AI must remain disabled, not merely that it currently is disabled → fixes Problem #4 (circular reasoning)
6. **Deleted Prohibited Use #6** (Copilot on FedRAMP-scoped workstreams) entirely → fixes Problem #5 (undefined "FedRAMP-scoped workstreams" is invented content) and Problem #6 (no enforcement mechanism existed for it)
7. **Added Enforcement item #5** covering Prohibited Uses #3 and #5 via existing code review and IT access controls → fixes Problem #7 (Prohibited Uses #3 and #5 had no enforcement mechanism)
8. **Rewrote Permitted Use #3** to restrict sales to GitHub Copilot Business only, matching the approved tool list → fixes Problem #10 (ambiguity permitting unapproved tools for sales)

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** [OWNER] | **Audience:** All Employees

---

## Scope

1. This policy applies to all employees, contractors, and interns across all functions.
2. This policy governs any use of AI tools—including code assistants, text generators, and chat interfaces—for work-related tasks.

---

## Permitted Uses

1. **Engineers:** GitHub Copilot Business seats are allocated by Engineering Leads via GitHub admin controls.
2. **Engineers:** AI-assisted code is permitted only when the committing engineer reviews, understands, and accepts ownership of every line before commit.
3. **Sales:** GitHub Copilot Business is permitted for internal draft generation using only non-confidential, non-customer data. All outbound content requires human review before sending.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data—including database schemas, records, or identifiers—into any third-party AI service is prohibited. *(Motivating facts: Engineer pasted a customer database schema into ChatGPT; outside counsel confirmed this likely violates existing DPA terms; company holds SOC2 Type II certification and GDPR obligations covering customer PII and financial data.)*
2. **No unverified AI-generated content in outbound communications.** Sending or publishing AI-generated text without confirming it contains no third-party copyrighted material is prohibited. *(Motivating fact: Sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim.)*
3. **No AI-generated code committed without license review.** Engineers must confirm no open-source license artifacts are present before committing AI-generated code. *(Motivating facts: Intern committed code containing a GPL header from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
4. **No unapproved AI tools for any work purpose.** Using any AI service other than GitHub Copilot Business for work tasks is prohibited. *(Motivating facts: Two prior-quarter incidents involved unapproved external tools; outside counsel confirmed inputting company or customer data into third-party AI services likely violates existing DPA terms.)*
5. **No enabling of AI features in company Slack.** Employees must not enable Slack AI features. *(Motivating facts: Enabling Slack AI features would route company data to a third-party AI service, which outside counsel confirmed likely violates existing DPA terms and which conflicts with SOC2 Type II and GDPR obligations covering customer PII and financial data.)*

---

## Enforcement

1. Engineering Leads review AI tool compliance during existing pull request and code review workflows; violations are referred to HR for disciplinary action.
2. Violations involving customer data (Prohibited Use #1) are escalated immediately to Legal and treated as a potential data incident under the existing SOC2 incident response process.
3. Sales Managers verify outbound content in existing deal review meetings; AI-generated content sent without human verification of originality is referred to HR for disciplinary action.
4. GitHub admin controls enforce seat allocation and access revocation for all GitHub Copilot Business usage.
5. Engineering Leads flag license artifacts during code review (Prohibited Use #3); IT enforces Slack AI feature access via existing administrative controls (Prohibited Use #5).