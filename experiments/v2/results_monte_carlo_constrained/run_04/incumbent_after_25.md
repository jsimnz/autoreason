I'll address each problem systematically, then present the revised document.

**Changes made and which problems they fix:**

- **Problem 1 (word count):** Cut Enforcement #1 entirely (also fixes Problem 6). Tightened parentheticals throughout. Condensed Permitted Use #2 and #4.
- **Problem 2 (aspirational language in Permitted Use #4):** Replaced "may be approved" with "requires written sign-off by Legal and Security, documented by IT, within the $50K annual budget" — a concrete gate, not a conditional.
- **Problem 3 (Prohibited Use #3 missing base fact):** Added explicit citation of the 45%-of-sales-using-AI base fact.
- **Problem 4 (Prohibited Use #5 missing base fact):** Replaced the inference with direct citation of the base fact: "company Slack has AI features disabled."
- **Problem 5 (FedRAMP as current obligation):** Changed Scope #3 to "pending FedRAMP authorization (Q3 target)" to match the base fact exactly.
- **Problem 6 (Enforcement #1 duplicates Permitted Use #1):** Deleted Enforcement #1; replaced with a new item addressing the IP ownership disclosure gap (also fixes Problem 8).
- **Problem 7 (sales staff policy vacuum):** Added a Permitted Use item explicitly addressing sales staff AI writing tool requests under the approval pathway.
- **Problem 8 (copyright non-copyrightability not addressed as standalone rule):** Added a new Enforcement item requiring employees to disclose AI-generated content in deliverables so IP ownership can be assessed, citing outside counsel's finding directly.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy applies to all 200 employees and interns.
2. This policy governs all use of AI-assisted tools for any work-related task.
3. This policy operates within the company's SOC2 Type II and GDPR compliance obligations, and the pending FedRAMP authorization targeted for Q3.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, capped at 80 seats provisioned and revoked by IT through existing access controls.
2. Engineers using GitHub Copilot Business must declare in each PR description that the submission contains no customer PII, financial data, or database schemas, and no third-party license notices. The reviewer must confirm both declarations before approving.
3. All AI-generated code must pass PR review under the standard review process.
4. Additional AI tools require written sign-off from both Legal and Security, documented by IT, within the $50K annual AI tooling budget. Sales staff seeking an approved AI writing tool must follow this process.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Incident #1; DPA violation risk per outside counsel; GDPR obligations; SOC2 Type II certification; pending FedRAMP authorization.)*
2. **No verbatim third-party copyrighted content.** Employees must not submit, send, or publish AI-generated content containing verbatim third-party copyrighted text. *(Incident #2: a sales rep submitted AI-generated text containing a competitor's copyrighted marketing copy verbatim.)*
3. **No unapproved AI writing tools.** Employees must not use any AI writing tool not approved under Permitted Use #4. *(Incident #2; 45% of sales staff are currently using unapproved AI writing tools per internal survey; inputting company or customer data into unapproved third-party AI services risks violating existing DPA terms per outside counsel.)*
4. **No committing AI-generated code containing third-party license notices.** *(Incident #3: an intern committed AI-generated code carrying a GPL license header from training data; outside counsel flagged that AI-generated code may not be copyrightable, making unresolved third-party license notices a direct IP liability.)*
5. **No re-enabling Slack AI features.** Employees must not re-enable any AI feature within the company Slack instance. *(Base fact: company Slack has AI features disabled; re-enabling constitutes use of a third-party AI service risking DPA violations per outside counsel; SOC2 Type II certification; pending FedRAMP authorization.)*

---

## Enforcement

1. Employees must disclose AI-generated content in any work deliverable at the time of submission, enabling Legal to assess IP ownership. *(Outside counsel flagged that AI-generated code may not be copyrightable.)*
2. A reviewer who approves a PR without the declarations required by Permitted Use #2 has committed a policy violation and is subject to item 4 of this section.
3. Suspected violations must be reported to Legal and Security via the existing incident reporting channel immediately upon discovery.
4. Confirmed violations result in suspension of AI tool access by IT, pending written reinstatement by the employee's manager and HR through the standard HR process.