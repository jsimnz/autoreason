# AI Tool Usage Policy
**Effective Date:** Date of CEO signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI tools used for any work purpose by all 200 employees, on any device. An informal survey found 73% of engineers and 45% of sales staff are already using AI tools; this policy applies retroactively from the effective date.
2. Approved tools at issuance: GitHub Copilot Business (80 licensed seats, managed by Engineering leadership). All other AI tools are unapproved unless Legal issues prior written approval following DPA and IP review.
3. Company Slack AI features are disabled by system configuration and are not an approved tool.
4. The company's allocated AI tooling budget is $50K/year. Requests for new tool approvals are evaluated against this budget by Legal and Finance.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, generation, and review in approved repositories. Engineers without an assigned seat have no approved AI coding tool.
2. Sales staff may use approved AI tools to draft external communications, provided no customer PII or financial data appears in any prompt or input.
3. All other employees (non-engineering, non-sales) have no approved AI tool at issuance. Any use requires prior written approval from Legal under Scope item 2.

---

## Prohibited Uses

1. **No customer data in unapproved AI tools.** Inputting PII, financial data, or any customer-identifiable information into any unapproved AI service is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel DPA violation finding; SOC2 Type II, GDPR, and pending FedRAMP obligations.]*
2. **No distribution of AI-generated content reproducing copyrighted material verbatim.** Employees must review AI-drafted content for verbatim third-party text before sending, publishing, or committing it. *[Basis: Incident 2—sales rep distributed AI text reproducing a competitor's copyrighted marketing copy verbatim; outside counsel IP risk finding.]*
3. **No unapproved AI tools.** Employees must not use any AI tool for work purposes other than tools approved under Scope item 2. *[Basis: Incidents 1, 2, and 3 each involved unapproved tools; outside counsel IP and DPA findings.]*
4. **No committing AI-generated code containing license identifiers without Legal clearance.** Engineers must flag any license strings found in AI-generated code during PR review and obtain Legal clearance before merging. *[Basis: Incident 3—intern committed AI-generated code containing a GPL license header; outside counsel copyright risk finding.]*
5. **No asserting company copyright over AI-generated code without Legal clearance.** Employees must not claim company ownership over AI-generated code without prior written clearance from Legal. *[Basis: Outside counsel finding that AI-generated code may not be copyrightable.]*
6. **No enabling Slack AI features.** Employees must not attempt to enable or use Slack AI features. *[Basis: Company Slack has AI features disabled by configuration; enabling them constitutes use of an unapproved tool under item 3.]*

---

## Enforcement

1. Violations involving customer PII or financial data (Prohibited Use item 1) constitute a Severity 1 security incident: Engineering leadership must file a report via the company's security incident reporting process within 24 hours; Legal must be notified for GDPR breach assessment and FedRAMP impact review. HR will conduct a disciplinary review; termination is a defined possible outcome.
2. Violations involving verbatim copyrighted content (Prohibited Use item 2) must be reported to Legal via the company's security incident reporting process immediately upon discovery; Legal will assess whether retraction or third-party notification is required. Disciplinary consequence: written warning for a first offense; repeat offenses are referred to HR for disciplinary review, with termination as a defined possible outcome.
3. All other violations (Prohibited Use items 3–6) must be reported to the employee's manager and to Legal via the company's security incident reporting process. Disciplinary consequence: written warning for a first offense; repeat offenses are referred to HR for disciplinary review, with termination as a defined possible outcome.

---

CEO Signature: ___________________________ Date: ___________________________