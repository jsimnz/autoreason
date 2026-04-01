# AI Tool Usage Policy

**TO:** All Employees, Contractors, and Interns
**FROM:** Office of the CEO
**DATE:** [DATE]
**RE:** AI Tool Usage Policy — Effective Immediately

---

## Scope

1. This policy applies to all employees, contractors, and interns performing work for the company.
2. It governs all AI-powered tools used for company work on company systems or networks.
3. It covers AI coding assistants, writing assistants, and any generative AI model producing code, text, or data.

---

## Permitted Uses

1. GitHub Copilot Business is the sole approved AI coding tool. Engineering leadership assigns the 80 licensed seats to named individuals via existing GitHub Copilot Business seat controls.
2. Seat-holders may use GitHub Copilot Business for code completion, boilerplate generation, and test writing.
3. All AI-generated code must pass the existing pull-request review process before merge.
4. Additional AI tools may be approved against the $50K annual AI tooling budget. Any request requires written approval from the relevant department head and Legal before use.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1; outside counsel confirmed this violates existing DPA terms; company holds GDPR obligations for EU customers and has pending FedRAMP authorization.]*
2. **No AI-generated external content without Legal review.** AI-generated text for external distribution requires Legal to confirm no third-party copyrighted material is present before sending. *[Basis: Incident 2; outside counsel flagged copyright infringement risk in AI-generated content.]*
3. **No commits with third-party license headers.** Pull-request reviewers must reject any commit carrying an AI-generated third-party license header. *[Basis: Incident 3; an intern committed AI-generated code carrying a GPL license header from AI training data.]*
4. **No unapproved AI tools.** No employee may use any AI tool not approved under Permitted Uses item 1 or the process in item 4. *[Basis: Incidents 1, 2, and 3 each involved unapproved or unsanctioned tool use; outside counsel confirmed inputting data into third-party AI services violates existing DPA terms; company holds GDPR obligations and has pending FedRAMP authorization.]*
5. **Slack AI features remain disabled.** No employee may enable AI features within company Slack. *[Basis: Slack AI features are currently disabled as an existing configuration; enabling them would route company data through a third-party AI service, violating existing DPA terms and GDPR obligations.]*
6. **No IP ownership assertion over AI output.** No employee may assert company copyright ownership over AI-generated code or content. *[Basis: Outside counsel confirmed AI-generated code and content may not be copyrightable.]*

---

## Enforcement

1. For code, the pull-request reviewer must confirm AI-generated content complies with this policy before approving any merge. For external written output, the submitting employee's direct manager must confirm compliance before the output is sent.
2. Any employee who discovers a violation must report it to Legal through the existing HR incident reporting process within one business day of discovery.
3. Upon Legal's confirmation of a violation, Legal must record the violation in the employee's HR file.
4. The violating employee's direct manager must conduct a review within five business days of Legal's confirmation.
5. If the violating employee holds a seat or access grant for an approved AI tool, Engineering leadership must revoke that access through existing seat controls upon Legal's confirmation.
6. HR must administer disciplinary action, up to and including termination, through the existing HR disciplinary process upon Legal's confirmation of a violation.