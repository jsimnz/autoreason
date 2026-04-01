I'll address each problem, then present the revised document.

**Changes made and which problem each fixes:**

1. **Preamble removed entirely** — fixes Problem 1. The deliverable is the policy memo only.

2. **Policy body rewritten to fit within 500 words** — fixes Problem 2. Word count is controlled throughout.

3. **Scope item 2 replaced with a substantive applicability statement** (covering personal/free-tier tools used for company work) — fixes Problem 3. All scope items now define who and what is covered.

4. **Scope item 3 removed** — fixes Problem 4. Enforcement methodology does not belong in Scope.

5. **Copyright non-assignability notice moved from Permitted Uses item 2 into Prohibited Uses as a new item** — fixes Problem 5. Prohibitions now appear only in Prohibited Uses.

6. **Enforcement item 5 rewritten** to apply the consequence based on whether the employee holds an approved AI tool seat: revocation if they do; if they do not, the manager review under item 4 constitutes the sole procedural consequence, and disciplinary outcome is determined under item 6 — fixes Problem 6.

7. **Enforcement item 6 added** stating that confirmed violations are subject to disciplinary action up to and including termination, consistent with existing HR policy — fixes Problem 7.

8. **"Designated copyright reviewer" removed; replaced with "Legal"** as the sole reviewer, which is derivable from the base facts — fixes Problem 8.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy applies to all employees, contractors, and interns performing work for the company.
2. It governs all AI-powered tools used for company work, including personal accounts and free-tier tools used for company purposes.
3. It covers AI coding assistants, writing assistants, and any generative AI model producing code, text, or data.

---

## Permitted Uses

1. GitHub Copilot Business is the sole approved AI coding tool. Engineering leadership assigns the 80 licensed seats to named individuals via existing GitHub Copilot Business seat controls.
2. Seat-holders may use GitHub Copilot Business for code completion, boilerplate generation, and test writing.
3. All AI-generated code must pass the existing pull-request review process before merge.
4. Additional AI tools require written approval from the relevant department head and Legal before use begins. No additional tool may be approved once total AI tooling spend reaches $50K/year; no further approvals occur until the next budget cycle.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1; outside counsel confirmed this violates existing DPA terms and GDPR obligations for EU customers.]*
2. **No AI-generated external content without Legal review.** AI-generated text for external distribution requires Legal to confirm no third-party copyrighted material is present before sending. *[Basis: Incident 2; outside counsel flagged copyright infringement risk in AI-generated content.]*
3. **No commits with third-party license headers.** Pull-request reviewers must reject any commit carrying an AI-generated third-party license header. *[Basis: Incident 3; intern committed AI-generated code carrying a GPL license header from AI training data.]*
4. **No unapproved AI tools.** No employee may use any AI tool not approved under Permitted Uses item 4. *[Basis: Outside counsel confirmed inputting data into third-party AI services violates existing DPA terms; company holds GDPR obligations for EU customers.]*
5. **Slack AI features remain disabled.** No employee may enable AI features within company Slack. *[Basis: Outside counsel confirmed inputting customer data into third-party AI services violates existing DPA terms; Slack processes customer PII and financial data.]*
6. **No IP ownership assertion over unmodified AI output.** Outside counsel confirmed AI-generated code and content may not be copyrightable; no employee may assert company copyright ownership over unmodified AI output.

---

## Enforcement

1. The assigned reviewer confirms AI-generated content complies with this policy before approving any code merge or approving any external output.
2. Any violation is reported to Legal through the existing Legal intake process within one business day of discovery.
3. Upon Legal's confirmation of a violation, the violation is recorded in the employee's HR file.
4. A confirmed violation triggers a mandatory manager review within five business days.
5. If the violating employee holds a seat or access grant for an approved AI tool, Engineering leadership revokes that access through existing seat controls. If the employee holds no such access, item 4 constitutes the procedural consequence.
6. Confirmed violations are subject to disciplinary action up to and including termination, administered through the existing HR disciplinary process.