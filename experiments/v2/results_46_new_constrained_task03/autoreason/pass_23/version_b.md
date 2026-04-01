I'll address each problem in turn, then present the revised document.

**Changes made and their justifications:**

- **Problem 1 (word count):** Cut Scope item 4 (budget process description), collapsed Scope item 3 into Scope item 2, removed redundant explanatory prose throughout, shortened enforcement items, and removed Prohibited Use item 6. See also Problems 2, 4, 7.
- **Problem 2 (prose items):** Converted multi-sentence explanatory items into tighter, discrete policy statements throughout all sections.
- **Problem 3 (null permission for sales):** Removed Permitted Use item 2. Sales staff have no approved AI tool at issuance; granting conditional permission for a non-existent approved tool is meaningless. Sales use requires prior written Legal approval under Scope item 2.
- **Problem 4 (redundant Slack prohibition):** Removed Prohibited Use item 6. The feature is disabled by configuration; no enforceable prohibition is needed or possible for ordinary employees.
- **Problem 5 (incoherent retroactivity):** Removed "retroactively" language. The policy applies from the effective date forward.
- **Problem 6 (FedRAMP not treated as standalone fact):** Added a standalone prohibition citing FedRAMP as the motivating base fact, covering AI tool use that could affect the pending FedRAMP authorization.
- **Problem 7 (Slack framing):** Revised Scope item 3 to state that Slack AI features are disabled by system configuration, without characterizing that as a policy approval decision.
- **Problem 8 (Engineering leadership for all Severity 1):** Replaced "Engineering leadership" with "the violating employee's manager" for incident reporting, applicable to all staff.

---

# AI Tool Usage Policy
**Effective Date:** Date of CEO signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI tools used for any work purpose by all employees, on any device.
2. Approved tools at issuance: GitHub Copilot Business (80 licensed seats, managed by Engineering). All other AI tools require prior written Legal approval following DPA and IP review before use.
3. Slack AI features are disabled by system configuration.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, generation, and review in approved repositories.
2. Engineers without an assigned seat have no approved AI coding tool.
3. All other employees have no approved AI tool at issuance; any use requires prior written Legal approval under Scope item 2.

---

## Prohibited Uses

1. **No customer data in AI inputs.** Employees must not input PII, financial data, or any customer-identifiable information into any AI service. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel DPA violation finding; SOC2 Type II and GDPR obligations.]*
2. **No AI-generated content reproducing copyrighted material.** Employees must review AI-drafted content for verbatim third-party text before sending, publishing, or committing it. *[Basis: Incident 2—sales rep distributed AI text reproducing a competitor's copyrighted marketing copy verbatim; outside counsel IP risk finding.]*
3. **No unapproved AI tools.** Employees must not use any AI tool for work purposes without approval under Scope item 2. *[Basis: Incidents 1, 2, and 3 each involved unapproved tools; outside counsel IP and DPA findings.]*
4. **No committing AI-generated code containing license identifiers without Legal clearance.** Engineers must flag license strings in AI-generated code during PR review and obtain Legal clearance before merging. *[Basis: Incident 3—intern committed AI-generated code containing a GPL license header; outside counsel copyright risk finding.]*
5. **No asserting company copyright over AI-generated code without Legal clearance.** Employees must not claim company ownership over AI-generated code without prior written Legal clearance. *[Basis: Outside counsel finding that AI-generated code may not be copyrightable.]*
6. **No AI tool use that could affect FedRAMP authorization.** Employees must not use any AI tool in systems or workflows within scope of the company's pending FedRAMP authorization without prior written Legal and Security approval. *[Basis: Pending FedRAMP authorization targeted for Q3; federal data handling requirements prohibit unapproved third-party service integrations in-scope.]*

---

## Enforcement

1. Violations of Prohibited Use item 1 constitute a Severity 1 security incident: the violating employee's manager must file a report via the security incident reporting process within 24 hours; Legal must be notified for GDPR breach assessment and FedRAMP impact review. HR will conduct a disciplinary review; termination is a defined possible outcome.
2. Violations of Prohibited Use item 2 must be reported to Legal immediately upon discovery; Legal will assess whether retraction or third-party notification is required. Consequence: written warning for a first offense; repeat offenses are referred to HR, with termination as a defined possible outcome.
3. All other violations must be reported to the employee's manager and to Legal. Consequence: written warning for a first offense; repeat offenses are referred to HR, with termination as a defined possible outcome.

---

CEO Signature: ___________________________ Date: ___________________________