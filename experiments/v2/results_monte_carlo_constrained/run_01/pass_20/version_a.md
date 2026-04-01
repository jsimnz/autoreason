I'll address each problem in turn, then present the revised document.

**Changes made and which problem each fixes:**

1. **Scope item 2 removed; replaced with a substantive scope item about AI-generated code copyright status** — fixes "Scope item 2 is administrative filler" and fixes "No mention of copyright non-assignability."

2. **Prohibited Use item 4 basis rewritten** to cite DPA terms (outside counsel finding) and GDPR obligations as the specific base facts, removing the unsupported FedRAMP inference — fixes "Prohibited Use item 4 partially fails the basis requirement" and "FedRAMP authorization exposure is not directly derivable."

3. **Prohibited Use item 5 basis rewritten** to cite outside counsel's finding that inputting data into third-party AI services violates DPA terms, and GDPR obligations, as the risk basis — fixes "Prohibited Use item 5 basis is circular."

4. **Permitted Uses item 4 rewritten** to state that additional tools require approval and must not cause total AI tooling spend to exceed $50K/year, with a clear consequence when budget is exhausted — fixes "enforcement gap when budget is exhausted."

5. **Permitted Uses item 2 amended** to note that AI-generated code carries no guaranteed copyright assignment, so ownership cannot be asserted — fixes "No mention of copyright non-assignability" (in conjunction with change 1).

6. **Prohibited Use item 2 rewritten** to require copyright review (not just manager approval) before external distribution — fixes "manager approval does not prevent copyright infringement."

7. **Enforcement item 5 broadened** to cover all confirmed violations, not only Copilot-related ones, specifying revocation of access to the relevant approved tool — fixes "Enforcement item 5 scope is too narrow."

8. **Enforcement item 3 given a specific trigger and process reference** (the existing Legal intake process, triggered by the same report required in item 2) — fixes "Enforcement item 3 has no stated trigger threshold or process reference."

9. **Word count reduced throughout** by cutting redundant phrases — fixes the word count constraint violation.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee for company work, including personal or free-tier tools used for company purposes.
2. AI-generated code and content may not be copyrightable; the company makes no ownership assertion over outputs produced by AI tools.
3. This policy is enforced using existing access controls, pull-request review processes, and HR procedures. No new tooling is required.

---

## Permitted Uses

1. GitHub Copilot Business is the sole approved AI coding tool. Engineering leadership assigns the 80 licensed seats to named individuals via existing GitHub Copilot Business seat controls.
2. Copilot-seated engineers may use GitHub Copilot Business for code completion, boilerplate generation, and test writing. Because AI-generated code carries no guaranteed copyright assignment, no IP ownership claim may be asserted over unmodified AI output.
3. AI-generated code must pass the existing pull-request review process before merge.
4. Additional AI tools require written approval from department head and Legal before use begins. Approved tools must not cause total AI tooling spend to exceed $50K/year. When the budget is exhausted, no further tools may be approved until the next budget cycle.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—engineer pasted a customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms and creates GDPR liability for EU customer data.]*
2. **No AI-generated external content without copyright review.** AI-generated text for external distribution requires Legal or a designated copyright reviewer to confirm no third-party copyrighted material is present before sending. *[Basis: Incident 2—sales rep distributed AI-generated text containing a competitor's copyrighted marketing copy verbatim; outside counsel flagged copyright infringement risk in AI-generated content.]*
3. **No commits with third-party license headers.** Reviewers must reject any pull request carrying an AI-generated third-party license header. *[Basis: Incident 3—intern committed AI-generated code carrying a GPL license header from AI training data.]*
4. **No unapproved AI tools.** No employee may use any AI tool not approved under Permitted Uses item 4. *[Basis: Outside counsel confirmed that inputting company or customer data into third-party AI services violates existing DPA terms; the company holds GDPR obligations for EU customers.]*
5. **Slack AI features remain disabled.** No employee may enable AI features within company Slack. *[Basis: Outside counsel confirmed that inputting customer data into third-party AI services violates existing DPA terms; enabling Slack AI features would expose customer PII and financial data processed through Slack to that risk.]*

---

## Enforcement

1. The assigned reviewer confirms AI-generated content complies with this policy before approving any code merge or external output.
2. Any violation is reported to Legal through the existing Legal intake process within one business day of discovery.
3. Upon Legal's confirmation of a violation via the intake process, the violation is recorded in the employee's HR file.
4. A confirmed violation triggers a mandatory manager review within five business days.
5. A confirmed violation results in Engineering leadership revoking the employee's access to the relevant approved AI tool through existing seat or access controls.