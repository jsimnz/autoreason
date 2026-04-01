I'll address each problem in turn, then present the revised document.

**Changes made and why:**

1. **Scope item 3 deleted** — fixes "Unnecessary Filler": it restated compliance obligations without adding an enforceable requirement.

2. **Permitted Use #2 and #3: removed the embedded enforcement cross-reference sentences** ("Approving without that confirmation is a policy violation by the reviewer, subject to Enforcement item 5") — fixes "Numbered items are not purely numbered items" and reduces word count toward the 500-word limit. The consequence is already stated in Enforcement item 2.

3. **Permitted Use #2: removed the restriction to "work that does not involve customer PII, financial data, or database schemas" as the sole condition** and replaced with a declaration requirement that covers both data sensitivity and copyright — fixes "Permitted Use #2 implies Copilot is cleared for non-PII work": outside counsel flagged the copyright risk as general, not limited to PII contexts. The PR gate now requires both declarations for all Copilot use.

4. **Prohibited Use #3: added DPA citation** — fixes "Prohibition #3 lacks a complete base-fact citation." Unapproved AI writing tools risk inputting company or customer data into third-party services with no DPA coverage, which outside counsel flagged. The citation now grounds the prohibition in that legal risk.

5. **Prohibited Use #5: rewritten to prohibit employees from re-enabling Slack AI features, rather than treating them as currently active** — fixes "Prohibited Use #5 asserts Slack AI features are currently active." The base fact is that they are already disabled; the prohibition targets the act of re-enabling them.

6. **Enforcement item 3: deleted** — fixes "Enforcement item 3 assumes a monitoring capability not established in the base facts." No base fact establishes that IT can detect re-enablement. Removing it keeps enforcement grounded in existing controls. The prohibition in Prohibited Use #5 and the general violation-reporting item (Enforcement item 4) cover this without assuming new capability.

7. **Enforcement item 2: removed circular self-reference** — fixes "Enforcement item 2 cross-references itself circularly." It now states the consequence directly rather than pointing to item 5.

8. **Word count reduced throughout** by cutting filler phrasing across all sections to bring the document within 500 words.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy applies to all 200 employees and interns.
2. This policy governs all use of AI-assisted tools for any work-related task.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, capped at 80 seats provisioned and revoked by IT through existing access controls.
2. Engineers using GitHub Copilot Business must declare in each PR description that the submission contains no customer PII, financial data, or database schemas, and contains no third-party license notices. The reviewer must confirm both declarations are present before approving.
3. All AI-generated code must pass PR review under the standard review process.
4. Additional AI tools may be approved upon written sign-off by Legal and Security, documented in writing and tracked by IT, within the $50K annual AI tooling budget.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Incident #1; DPA violation risk per outside counsel; GDPR obligations; SOC2 Type II; pending FedRAMP authorization.)*
2. **No verbatim third-party copyrighted content.** Employees must not submit, send, or publish AI-generated content containing verbatim third-party copyrighted text. *(Incident #2: sales rep submitted AI-generated text containing a competitor's copyrighted marketing copy verbatim.)*
3. **No unapproved AI writing tools.** Employees must not use any AI writing tool not approved under Permitted Use #4. *(Incident #2; inputting company or customer data into unapproved third-party AI services risks violating existing DPA terms per outside counsel.)*
4. **No committing AI-generated code containing third-party license notices.** *(Incident #3: an intern committed AI-generated code carrying a GPL license header from training data; outside counsel flagged that AI-generated code may not be copyrightable, making unresolved third-party license notices a direct IP liability.)*
5. **No re-enabling Slack AI features.** Employees must not re-enable any AI feature within the company Slack instance. *(Doing so would constitute use of a third-party AI service, risking violation of existing DPA terms per outside counsel; SOC2 Type II; pending FedRAMP authorization.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing access controls, within the 80-seat hard cap.
2. A reviewer who approves a PR without the declarations required by Permitted Use #2 has committed a policy violation. Confirmed violations result in suspension of AI tool access by IT, pending written reinstatement by the employee's manager and HR through the standard HR process.
3. Suspected violations must be reported to Legal and Security via the existing incident reporting channel immediately upon discovery.
4. Confirmed violations result in suspension of AI tool access by IT, pending written reinstatement by the employee's manager and HR through the standard HR process.