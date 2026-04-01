# AI Tool Usage Policy
**Effective Date:** Date of CEO signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI tools used for any work purpose by all employees, on any device, from the effective date forward.
2. Approved tools at issuance: GitHub Copilot Business (80 licensed seats, managed by Engineering). All other AI tools require prior written Legal approval following DPA and IP review before use.
3. Slack AI features are disabled by system configuration and are not an approved tool.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, generation, and review in approved repositories.
2. Sales employees have no approved AI tool at issuance. Legal must complete DPA and IP review of a sales-appropriate tool within 60 days, funded from the $50K AI tooling budget, and submit a recommendation to the CEO.
3. All other employees have no approved AI tool at issuance; any use requires prior written Legal approval under Scope item 2.

---

## Prohibited Uses

1. **No customer data in AI inputs.** Employees must not input PII, financial data, or any customer-identifiable information into any AI service. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel DPA violation finding; SOC2 Type II and GDPR obligations; pending FedRAMP authorization.]*
2. **No AI-generated content reproducing copyrighted material verbatim.** Employees must review AI-drafted content for verbatim third-party text before sending, publishing, or committing it. *[Basis: Incident 2—sales rep distributed AI text reproducing a competitor's copyrighted marketing copy verbatim; outside counsel IP risk finding.]*
3. **No committing AI-generated code containing license identifiers without Legal clearance.** Engineers must flag license strings in AI-generated code during PR review and obtain Legal clearance before merging. *[Basis: Incident 3—intern committed AI-generated code containing a GPL license header; outside counsel finding that AI-generated code may not be copyrightable.]*
4. **No AI tool use in FedRAMP-scoped systems or workflows without approval.** Employees must not use any AI tool in systems or workflows within scope of the pending FedRAMP authorization without prior written Legal and Security approval. *[Basis: Pending FedRAMP authorization targeted for Q3.]*

---

## Enforcement

1. **Prohibited Use item 1 violations (Severity 1 security incident):**
   - 1a. The violating employee must report the violation to their manager immediately upon discovery.
   - 1b. The manager must file a security incident report within 24 hours of notification.
   - 1c. Legal must be notified immediately for GDPR breach assessment; supervisory authority notification under GDPR Article 33 must occur within 72 hours of the company becoming aware of the breach.
   - 1d. HR will conduct a disciplinary review; termination is a defined possible outcome.
2. **Prohibited Use item 2 violations:**
   - 2a. The discovering employee must report to Legal via the security incident process immediately upon discovery.
   - 2b. Legal will assess whether retraction or third-party notification is required.
   - 2c. Consequence: written warning for a first offense; repeat offenses are referred to HR, with termination as a defined possible outcome.
3. **All other violations:**
   - 3a. The violating employee must report to their manager and Legal via the security incident process immediately upon discovery.
   - 3b. Consequence: written warning for a first offense; repeat offenses are referred to HR, with termination as a defined possible outcome.

---

CEO Signature: ___________________________ Date: ___________________________