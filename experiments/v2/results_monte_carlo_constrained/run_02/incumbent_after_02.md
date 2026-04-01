I'll address each problem systematically before presenting the revised document.

**Changes made and problems each fixes:**

1. **Removed "unused seats reallocated quarterly" from Permitted Use #1** → fixes invented content (no reallocation cadence in base facts)
2. **Removed Permitted Use #5 (FedRAMP/Copilot advisory)** and moved the substance into Prohibited Uses as a clear rule → fixes miscategorized section and aspirational "Confirm with Legal" language
3. **Removed Permitted Use #4 (Finance pre-approval process)** → fixes poor fit under Permitted Uses; budget fact is captured in Prohibited Use #4 as the basis for banning unapproved tools
4. **Rewrote Prohibited Use #4 motivating fact** to cite the DPA violation risk and the three incidents (all involving unapproved external tools), not the survey → fixes wrong motivation cited
5. **Rewrote Prohibited Use #5 motivating fact** to cite only that Slack AI features are already disabled (the base fact), removing the FedRAMP inference → fixes non-derivable inference
6. **Added new Prohibited Use #6** covering use of Copilot on FedRAMP-scoped workstreams pending Q3 authorization → fixes the miscategorized Permitted Use #5, now correctly placed as a prohibition with a clear rule
7. **Removed Enforcement item #5** (retroactive classification) → fixes invented content with no basis in base facts
8. **Removed specific "written warning/second offense revocation" escalation structure** from Enforcement → fixes invented disciplinary scale
9. **Moved "all other tools unapproved" language out of Scope** into Prohibited Uses where it belongs → fixes structural redundancy and miscategorization
10. **Rewrote Enforcement item #4** to address sending unverified AI content (the actual prohibition) rather than "undisclosed AI use" → fixes missing enforcement for Prohibited Use #2
11. **Cut throughout for word count** → fixes the 500-word constraint violation

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Audience:** All Employees

---

## Scope

1. This policy applies to all employees, contractors, and interns across all functions.
2. This policy governs any use of AI tools—including code assistants, text generators, and chat interfaces—for work-related tasks.

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
4. GitHub admin controls are used to enforce seat allocation and access revocation.