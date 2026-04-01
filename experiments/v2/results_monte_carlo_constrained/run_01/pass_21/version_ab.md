I'll identify the strongest element from each version per dimension, then present the synthesis.

**Dimension-by-dimension selection:**

- **Header format:** Version X (TO/FROM/DATE/RE memo header) — more formal and enforceable as a memo artifact than Y's inline metadata strip.
- **Scope:** Both are identical; either works.
- **Permitted Uses — sales AI use:** Version X explicitly addresses the 45% of sales staff already using AI for email drafting. Version Y omits this entirely, leaving a known-active population ungoverned. X wins.
- **Permitted Uses — budget tracking:** Version X assigns tracking responsibility to the department head and Legal within the existing approval workflow, making it auditable without new tooling. Y states the cap as a condition but assigns no one to track it. X wins.
- **Prohibited Use 5 (Slack):** Version X cites the actual base fact (Slack AI features are already disabled per company configuration) without adding inference. Y adds an inference ("Slack processes customer PII") not derivable from the base facts as a direct citation. X wins on constraint compliance.
- **Prohibited Use 6 (IP ownership):** Version X uses the bracketed *[Basis: ...]* format matching all other prohibitions, maintaining structural consistency. Y embeds the basis in prose, breaking the pattern. X wins.
- **Enforcement item 5:** Version X applies mandatory manager review universally and adds access revocation only where access exists, making both consequences explicit and neither subordinate to the other. Y frames the manager review as "the procedural consequence" only when no access exists, implying it is a lesser outcome for that population. X wins.
- **Enforcement — reporting mechanism:** Version X specifies "direct written notice to Legal" — concrete and derivable. Y retains "existing Legal intake process," which is not derivable from the base facts. X wins.
- **Word count discipline:** Version Y's Permitted Uses is tighter (4 items vs. X's 5). Y's Scope is identical. The synthesis must stay under 500 words; X's fuller Permitted Uses section requires careful trimming.

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
4. Sales staff may use AI tools for internal email drafting only. Any such tool requires prior written approval from the Sales department head and Legal before use begins, and is subject to Prohibited Uses item 2.
5. Any additional AI tool not covered by items 1 or 4 requires written approval from the relevant department head and Legal before use begins. The approving department head and Legal confirm available budget against the $50K/year AI tooling limit before granting approval; no approval is granted if the limit has been reached until the next budget cycle.

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