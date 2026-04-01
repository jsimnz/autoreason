# AI Tool Usage Policy
**Effective Date:** Date of CEO signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI tools used for any work purpose by all employees, on any device, from the effective date forward.
2. Approved tools at issuance: GitHub Copilot Business (80 licensed seats, managed by Engineering). All other AI tools require prior written Legal approval following DPA and IP review before use.
3. Slack AI features are disabled and are not an approved tool.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, generation, and review in approved repositories.
2. Sales employees currently using unapproved AI tools must cease that use within 14 days of the effective date. Continued or new use of any AI tool by sales employees requires prior written Legal approval under Scope item 2.
3. All other employees have no approved AI tool at issuance; any use requires prior written Legal approval under Scope item 2.

---

## Prohibited Uses

1. **No customer data in AI inputs.** Employees must not input PII, financial data, or any customer-identifiable information into any AI service. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel DPA violation finding; SOC2 Type II and GDPR obligations; pending FedRAMP authorization.]*
2. **No distributing AI-generated content without review.** The employee who generates AI-drafted content must review it for verbatim third-party text before sending, publishing, or committing it. *[Basis: Incident 2—sales rep distributed AI text reproducing a competitor's copyrighted marketing copy verbatim; outside counsel IP risk finding.]*
3. **No committing AI-generated code containing license identifiers without Legal clearance.** Engineers must flag license strings in AI-generated code during PR review and obtain Legal clearance before merging. *[Basis: Incident 3—intern committed AI-generated code containing a GPL license header.]*
4. **No representing AI-generated code as original company IP without Legal clearance.** Engineers must disclose AI-generated code in PR review; Legal clearance is required before asserting ownership. *[Basis: Outside counsel finding that AI-generated code may not be copyrightable.]*

---

## Enforcement

1. Violations of Prohibited Use item 1 are Severity 1 security incidents; the violating employee must report to their manager immediately upon discovery.
2. The manager must file a security incident report within 24 hours of notification of a Prohibited Use item 1 violation.
3. Legal must assess whether a notifiable personal data breach has occurred under GDPR and act accordingly within the applicable regulatory timeframe.
4. HR will conduct a disciplinary review for Prohibited Use item 1 violations; termination is a defined possible outcome.
5. The employee who generated and distributed content in violation of Prohibited Use item 2 must report to Legal via the security incident process immediately upon discovery.
6. Legal will assess whether retraction or third-party notification is required for Prohibited Use item 2 violations.
7. Prohibited Use item 2 first offense results in a written warning; repeat offenses are referred to HR, with termination as a defined possible outcome.
8. All other violations must be reported by the violating employee to their manager and Legal via the security incident process immediately upon discovery.
9. All other violations: first offense results in a written warning; repeat offenses are referred to HR, with termination as a defined possible outcome.

---

CEO Signature: ___________________________ Date: ___________________________