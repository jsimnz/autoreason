I'll address each problem, then present the revised document.

**Changes made and which problem each fixes:**

1. **Meta-commentary preamble removed entirely** — fixes Problem 1.

2. **TO/FROM/RE fields added to memo header** — fixes Problem 2.

3. **Prohibited Use 5 basis citation replaced** with the actual base fact: Slack AI features are already disabled per company configuration — fixes Problem 3. No inference about why they were disabled is added.

4. **Prohibited Use 6 reformatted** to include an explicit bracketed *[Basis: ...]* citation matching the format of all other prohibitions — fixes Problem 4.

5. **Budget cap language revised** to assign tracking responsibility to the department head and Legal as part of the written approval process, using the existing approval workflow rather than a new monitoring tool — fixes Problem 5.

6. **Sales AI use addressed explicitly** in Permitted Uses: sales staff may use AI for internal email drafting only under the written approval pathway, subject to Prohibited Use 2 — fixes Problem 6.

7. **Enforcement item 5 revised** to apply the same procedural consequence (manager review plus access revocation where applicable) to all violators; access revocation applies only where access exists, but the mandatory manager review applies universally and is not characterized as a lesser outcome — fixes Problem 7.

8. **"Existing Legal intake process" replaced** with a concrete, derivable reporting mechanism: direct written notice to Legal — fixes Problem 8.

---

# AI Tool Usage Policy

**TO:** All Employees, Contractors, and Interns
**FROM:** Legal & Engineering
**DATE:** [DATE]
**RE:** AI Tool Usage Policy — Effective Immediately

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
4. Sales staff may use AI tools for internal email drafting only. Any such tool requires prior written approval from the Sales department head and Legal before use begins. Approved sales AI use is subject to Prohibited Uses item 2.
5. Any additional AI tool not covered by items 1 or 4 requires written approval from the relevant department head and Legal before use begins. The approving department head and Legal confirm available budget against the $50K/year AI tooling limit before granting approval; no approval is granted if the limit has been reached, until the next budget cycle.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1; outside counsel confirmed this violates existing DPA terms and GDPR obligations for EU customers.]*
2. **No AI-generated external content without Legal review.** AI-generated text for external distribution requires Legal to confirm no third-party copyrighted material is present before sending. *[Basis: Incident 2; outside counsel flagged copyright infringement risk in AI-generated content.]*
3. **No commits with third-party license headers.** Pull-request reviewers must reject any commit carrying an AI-generated third-party license header. *[Basis: Incident 3; an intern committed AI-generated code carrying a GPL license header from AI training data.]*
4. **No unapproved AI tools.** No employee may use any AI tool not approved under Permitted Uses items 1, 4, or 5. *[Basis: Outside counsel confirmed inputting data into third-party AI services violates existing DPA terms; company holds GDPR obligations for EU customers.]*
5. **Slack AI features remain disabled.** No employee may enable AI features within company Slack. *[Basis: AI features in company Slack are currently disabled per company configuration.]*
6. **No IP ownership assertion over unmodified AI output.** No employee may assert company copyright ownership over unmodified AI-generated code or content. *[Basis: Outside counsel confirmed AI-generated code and content may not be copyrightable.]*

---

## Enforcement

1. The assigned reviewer confirms AI-generated content complies with this policy before approving any code merge or approving any external output.
2. Any violation is reported to Legal by written notice within one business day of discovery.
3. Upon Legal's confirmation of a violation, the violation is recorded in the employee's HR file.
4. A confirmed violation triggers a mandatory manager review within five business days. This requirement applies to all employees regardless of whether they hold an approved AI tool seat.
5. If the violating employee holds a seat or access grant for an approved AI tool, Engineering leadership revokes that access through existing seat controls upon Legal's confirmation of the violation.
6. Confirmed violations are subject to disciplinary action up to and including termination, administered through the existing HR disciplinary process.